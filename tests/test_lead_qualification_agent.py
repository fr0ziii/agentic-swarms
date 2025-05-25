import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure the agent module can be imported. Adjust path if necessary.
from backend.agents.lead_qualification.agent import LeadQualificationAgent
# Import classes to be mocked if needed for isinstance checks or type hints, though not strictly necessary for mocking.
# from backend.providers.multi_provider import MultiProvider 
# from backend.database.supabase_client import SupabaseClient
# from backend.agents.lead_qualification.tools import LeadQualificationTools


class TestLeadQualificationAgent(unittest.TestCase):

    def setUp(self):
        """Set up for each test method."""
        # Mock environment variables that LeadQualificationTools might read during its __init__
        # These are for the tools' initialization, even if the tools instance itself is mocked.
        self.mock_env_vars = {
            "LINKEDIN_SCRAPER_API_KEY": "fake_linkedin_key",
            "HUNTER_API_KEY": "fake_hunter_key",
            "CRM_WEBHOOK_URL": "https://fake.webhook.url"
        }
        self.env_patch = patch.dict(os.environ, self.mock_env_vars)
        self.env_patch.start()

        # Mock dependencies for LeadQualificationAgent
        self.mock_multi_provider = AsyncMock()
        self.mock_supabase_client = AsyncMock()
        
        # Mock the LeadQualificationTools instance and its methods
        self.mock_tools_instance = AsyncMock()
        
        # Configure return values for each tool method
        self.mock_tools_instance.linkedin_profile_scraper = AsyncMock()
        self.mock_tools_instance.company_research = AsyncMock()
        self.mock_tools_instance.qualification_score = AsyncMock()
        self.mock_tools_instance.crm_update = AsyncMock()

        # Patch the LeadQualificationTools class to return our mock_tools_instance when instantiated
        # This ensures that when LeadQualificationAgent creates its self.tools, it gets our mock
        self.tools_patcher = patch('backend.agents.lead_qualification.agent.LeadQualificationTools', return_value=self.mock_tools_instance)
        self.MockLeadQualificationTools = self.tools_patcher.start()

        # Initialize the agent with mocked dependencies
        self.agent = LeadQualificationAgent(
            multi_provider=self.mock_multi_provider,
            supabase_client=self.mock_supabase_client
        )
        # This explicit assignment ensures the agent's tool instance is our mock,
        # useful if __init__ logic changes or if patching strategy needs to be more direct.
        self.agent.tools = self.mock_tools_instance


    def tearDown(self):
        """Clean up after each test method."""
        self.env_patch.stop()
        self.tools_patcher.stop()

    def test_get_icp_criteria(self):
        """Verify that _get_icp_criteria returns the expected ICP structure."""
        # This is a synchronous method
        icp_criteria = self.agent._get_icp_criteria() 
        self.assertIsInstance(icp_criteria, dict)
        self.assertIn("company_size_range", icp_criteria)
        self.assertIn("company_size_weight", icp_criteria)
        self.assertIn("budget_authority_keywords", icp_criteria)
        self.assertIn("pain_point_keywords", icp_criteria)
        self.assertIn("engagement_min_summary_length", icp_criteria)
        self.assertGreater(len(icp_criteria["budget_authority_keywords"]), 0)


    async def test_qualify_lead_success(self):
        """Test successful lead qualification flow."""
        linkedin_url = "https://linkedin.com/in/testlead"
        company_domain = "testcompany.com"

        # Mock tool responses
        mock_linkedin_data = {
            "name": "Test Lead", "current_title": "CEO", "current_company": "TestCompany Inc (from LinkedIn)",
            "summary_about_section": "Experienced leader driving innovation and scaling challenges.", "profile_url": linkedin_url,
            "work_experience": [], "education": [], "skills": [] # Ensure all expected fields are present
        }
        self.mock_tools_instance.linkedin_profile_scraper.return_value = mock_linkedin_data
        
        mock_company_data = {
            "company_name": "TestCompany Inc (from Company Research)", "description": "A company solving problems.",
            "employee_count": 100, "industry": "Tech", "domain": company_domain, "location": "Test City"
        }
        self.mock_tools_instance.company_research.return_value = mock_company_data

        # Mock LLM response (MultiProvider.complete)
        mock_llm_response_content = {
            "observation": "LLM observation: Lead is CEO at a tech company of 100 employees. Summary mentions scaling challenges.",
            "reasoning": "LLM reasoning: Strong fit based on title and company size. Pain points mentioned.",
            "score": 0, # Placeholder, will be overwritten
            "recommendation": "", # Placeholder
            "next_action": "Send personalized email.",
            "personalization_hooks": ["Mention scaling challenges.", "Refer to CEO role."],
            "confidence": 0.9,
            "tools_used": [] # LLM does not call tools in the new flow
        }
        # Simulate the structure of the provider's response object
        mock_provider_response = MagicMock() # Synchronous MagicMock for the response object itself
        mock_provider_response.content = json.dumps(mock_llm_response_content) # Content is a JSON string
        self.mock_multi_provider.complete.return_value = mock_provider_response # complete is an AsyncMock

        # Mock qualification_score response
        mock_score_result = {"score": 85, "recommendation": "pursue", "reasoning": "System score: High match on ICP."}
        self.mock_tools_instance.qualification_score.return_value = mock_score_result

        # Mock crm_update response
        self.mock_tools_instance.crm_update.return_value = {"status": "success", "message": "CRM updated."}
        
        # Mock Supabase store_memory
        self.mock_supabase_client.store_memory = AsyncMock(return_value=None)

        # Call the method
        result = await self.agent.qualify_lead(linkedin_url, company_domain)

        # Assertions
        self.mock_tools_instance.linkedin_profile_scraper.assert_called_once_with(linkedin_url)
        self.mock_tools_instance.company_research.assert_called_once_with(company_domain)
        self.mock_multi_provider.complete.assert_called_once() 
        
        # Construct the expected profile_data that qualification_score receives
        expected_profile_for_score = {"profile_url": linkedin_url, "domain": company_domain}
        expected_profile_for_score.update(mock_linkedin_data)
        expected_profile_for_score.update(mock_company_data)
        expected_profile_for_score["lead_name"] = mock_linkedin_data.get("name")
        expected_profile_for_score["company_name"] = mock_company_data.get("company_name")


        self.mock_tools_instance.qualification_score.assert_called_once_with(
            profile=expected_profile_for_score,
            icp_config=self.agent._get_icp_criteria() 
        )

        self.assertEqual(result["score"], mock_score_result["score"])
        self.assertEqual(result["recommendation"], mock_score_result["recommendation"])
        self.assertIn(mock_llm_response_content["observation"], result["observation"])
        self.assertIn(mock_llm_response_content["reasoning"], result["reasoning"])
        self.assertIn(mock_score_result["reasoning"], result["reasoning"])
        self.assertEqual(result["next_action"], mock_llm_response_content["next_action"])

        self.mock_supabase_client.store_memory.assert_called_once()
        self.mock_tools_instance.crm_update.assert_called_once()


    async def test_qualify_lead_tool_failure_linkedin(self):
        """Test lead qualification when LinkedIn scraper fails."""
        linkedin_url = "https://linkedin.com/in/faillink"
        company_domain = "failcompany.com"

        self.mock_tools_instance.linkedin_profile_scraper.return_value = {"error": "LinkedIn scrape failed majorly"}
        self.mock_tools_instance.company_research.return_value = { 
            "company_name": "FailCompany", "employee_count": 50, "domain": company_domain,
            "description": "Some description", "location":"Some Location", "industry":"Tech"
        }
        
        mock_llm_response_content = {
            "observation": "LLM: LinkedIn data missing, company info available.",
            "reasoning": "LLM: Partial assessment due to missing LinkedIn data.",
            "next_action": "Manual review needed.", "personalization_hooks": [], "confidence": 0.3
        }
        mock_provider_response = MagicMock()
        mock_provider_response.content = json.dumps(mock_llm_response_content)
        self.mock_multi_provider.complete.return_value = mock_provider_response

        self.mock_tools_instance.qualification_score.return_value = {"score": 20, "recommendation": "disqualify", "reasoning": "Low score due to missing data."}

        result = await self.agent.qualify_lead(linkedin_url, company_domain)
        
        self.assertNotIn("error", result) # The overall process should complete and return a valid structure
        self.assertIn("linkedin_error", result["raw_profile_data_summary"]["linkedin_data_retrieved"])
        self.assertEqual(result["score"], 20)
        self.assertEqual(result["recommendation"], "disqualify")
        self.assertIn(mock_llm_response_content["observation"], result["observation"])
        self.mock_tools_instance.crm_update.assert_not_called() 


    async def test_qualify_lead_llm_failure(self):
        """Test lead qualification when LLM call fails."""
        linkedin_url = "https://linkedin.com/in/llmfail"
        company_domain = "llmfail.com"

        self.mock_tools_instance.linkedin_profile_scraper.return_value = {"name": "LLM Fail Lead", "current_title": "Good Title"}
        self.mock_tools_instance.company_research.return_value = {"company_name": "LLMFail Corp", "employee_count": 60}
        
        self.mock_multi_provider.complete.side_effect = Exception("LLM API Error")
        
        result = await self.agent.qualify_lead(linkedin_url, company_domain)
        
        self.assertIn("error", result)
        self.assertIn("LLM API Error", result["error"])
        self.assertEqual(result["recommendation"], "disqualify")
        self.assertEqual(result["score"], 0) 
        self.mock_tools_instance.qualification_score.assert_not_called() 
        self.mock_supabase_client.store_memory.assert_called_once() 
        self.mock_tools_instance.crm_update.assert_not_called()


    async def test_qualify_lead_no_company_domain(self):
        """Test lead qualification when no company domain is provided."""
        linkedin_url = "https://linkedin.com/in/nodomainlead"

        mock_linkedin_data = {"name": "No Domain Lead", "current_title": "Freelancer", "summary_about_section": "Independent consultant for various projects.", "profile_url": linkedin_url}
        self.mock_tools_instance.linkedin_profile_scraper.return_value = mock_linkedin_data
        
        mock_llm_response_content = {"observation": "LLM: Only LinkedIn data available. Company context missing.", "reasoning": "LLM: Assessment based on profile only.", "next_action": "Try to find company info or nurture based on individual profile.", "personalization_hooks": ["Ask about their freelance projects"], "confidence": 0.5}
        mock_provider_response = MagicMock()
        mock_provider_response.content = json.dumps(mock_llm_response_content)
        self.mock_multi_provider.complete.return_value = mock_provider_response
        
        self.mock_tools_instance.qualification_score.return_value = {"score": 20, "recommendation": "disqualify", "reasoning": "Score based on LinkedIn profile only, company data missing."} # Example score

        result = await self.agent.qualify_lead(linkedin_url, None) 

        self.mock_tools_instance.company_research.assert_not_called()
        self.assertEqual(result["score"], 20)
        self.assertEqual(result["recommendation"], "disqualify")
        self.assertEqual(result["domain"], "N/A") # Check how domain is handled
        self.mock_tools_instance.crm_update.assert_not_called() 


if __name__ == '__main__':
    # This block is primarily for making the file runnable and providing guidance.
    # For actual test execution, especially with async tests, using a test runner like pytest is standard.
    print("\nTests for LeadQualificationAgent created.")
    print("To run these tests, use a suitable test runner that supports asyncio, such as:")
    print("  pytest tests/test_lead_qualification_agent.py")
    print("\nIf you need to run with standard unittest and have Python 3.8+, you can use unittest.IsolatedAsyncioTestCase.")
    print("Alternatively, adapt the test methods to use asyncio.run() internally for each async test if not using a specialized runner.")
    
    # Example of how one might adapt for `python -m unittest discover` if needed (Python 3.8+):
    # Change `class TestLeadQualificationAgent(unittest.TestCase):`
    # to `class TestLeadQualificationAgent(unittest.IsolatedAsyncioTestCase):`
    # then `unittest.main()` could be called.
    # For now, pytest is the recommended approach.
    # unittest.main() # This would require the class to be IsolatedAsyncioTestCase or tests to be synchronous.
