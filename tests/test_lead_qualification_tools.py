import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Ensure the tools module can be imported. Adjust path if necessary.
# This might require adding the project root to PYTHONPATH or using relative imports if tests are part of a package.
from backend.agents.lead_qualification.tools import LeadQualificationTools

class TestLeadQualificationTools(unittest.TestCase):

    def setUp(self):
        """Set up for each test method."""
        # Mock environment variables for API keys
        self.mock_env_vars = {
            "LINKEDIN_SCRAPER_API_KEY": "test_linkedin_key",
            "HUNTER_API_KEY": "test_hunter_key",
            "CRM_WEBHOOK_URL": "https://example.com/fake_crm_webhook"
        }
        self.env_patch = patch.dict(os.environ, self.mock_env_vars)
        self.env_patch.start()
        self.tools = LeadQualificationTools()

    def tearDown(self):
        """Clean up after each test method."""
        self.env_patch.stop()

    # --- linkedin_profile_scraper Tests ---

    @patch('requests.post')
    async def test_linkedin_profile_scraper_success(self, mock_post):
        """Test successful LinkedIn profile scraping."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # This API is trigger-based, so it doesn't return full profile data directly.
        # The tool simulates a synchronous return for now.
        mock_response.json.return_value = {"collection_id": "some_id", "status": "pending"}
        mock_post.return_value = mock_response

        profile_url = "https://www.linkedin.com/in/johndoe"
        result = await self.tools.linkedin_profile_scraper(profile_url)

        mock_post.assert_called_once()
        self.assertNotIn("error", result)
        self.assertEqual(result["profile_url"], profile_url)
        # Check for simulated fields (as the actual API is async)
        self.assertIn("name", result)
        self.assertIn("current_title", result)
        self.assertIn("summary_about_section", result)
        self.assertTrue(result["raw_brightdata_response_simulation_note"])


    @patch('requests.post')
    async def test_linkedin_profile_scraper_api_error(self, mock_post):
        """Test LinkedIn scraper API error."""
        mock_post.side_effect = requests.exceptions.RequestException("API call failed")
        profile_url = "https://www.linkedin.com/in/johndoe"
        result = await self.tools.linkedin_profile_scraper(profile_url)
        self.assertIn("error", result)
        self.assertIn("Failed to trigger LinkedIn profile scrape", result["error"])

    async def test_linkedin_profile_scraper_no_api_key(self):
        """Test LinkedIn scraper with no API key."""
        with patch.dict(os.environ, {"LINKEDIN_SCRAPER_API_KEY": ""}):
            tools_no_key = LeadQualificationTools() # Re-initialize with changed env
            profile_url = "https://www.linkedin.com/in/johndoe"
            result = await tools_no_key.linkedin_profile_scraper(profile_url)
            self.assertIn("error", result)
            self.assertEqual(result["error"], "LINKEDIN_SCRAPER_API_KEY not found in environment variables.")

    # --- company_research Tests ---

    @patch('requests.get') # Hunter.io uses GET
    async def test_company_research_success(self, mock_get):
        """Test successful company research."""
        mock_api_response = {
            "data": {
                "name": "TestCorp",
                "description": "A test company.",
                "location": "Test City, Test Country",
                "domain": "testcorp.com",
                "metrics": {"employees": "101-250"}, # Example range
                "category": {"industry": "Technology"}
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        domain = "testcorp.com"
        result = await self.tools.company_research(domain)
        
        mock_get.assert_called_once()
        self.assertNotIn("error", result)
        self.assertEqual(result["company_name"], "TestCorp")
        self.assertEqual(result["description"], "A test company.")
        self.assertEqual(result["location"], "Test City, Test Country")
        self.assertEqual(result["employee_count"], (101 + 250) // 2) # Check parsing
        self.assertEqual(result["industry"], "Technology")
        self.assertEqual(result["domain"], domain)

    @patch('requests.get')
    async def test_company_research_missing_data(self, mock_get):
        """Test company research with some data missing from API response."""
        mock_api_response = {
            "data": { # Missing description, location, industry, employees
                "name": "TestCorp Partial",
                "domain": "partial.com"
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_response
        mock_get.return_value = mock_response

        domain = "partial.com"
        result = await self.tools.company_research(domain)

        self.assertNotIn("error", result)
        self.assertEqual(result["company_name"], "TestCorp Partial")
        self.assertEqual(result["description"], "N/A") # Default value
        self.assertIsNone(result["employee_count"]) # Should be None if missing
        self.assertEqual(result["industry"], "N/A") # Default value


    @patch('requests.get')
    async def test_company_research_api_error(self, mock_get):
        """Test company research API error."""
        mock_get.side_effect = requests.exceptions.RequestException("Hunter API call failed")
        domain = "errorcorp.com"
        result = await self.tools.company_research(domain)
        self.assertIn("error", result)
        self.assertIn("Failed to fetch data from Hunter.io", result["error"])


    async def test_company_research_no_api_key(self):
        """Test company research with no API key."""
        with patch.dict(os.environ, {"HUNTER_API_KEY": ""}):
            tools_no_key = LeadQualificationTools()
            domain = "testcorp.com"
            result = await tools_no_key.company_research(domain)
            self.assertIn("error", result)
            self.assertEqual(result["error"], "HUNTER_API_KEY not found in environment variables.")

    # --- crm_update Tests ---

    @patch('requests.post')
    async def test_crm_update_success(self, mock_post):
        """Test successful CRM update."""
        mock_response = MagicMock()
        mock_response.status_code = 200 # Success
        mock_response.text = "CRM Updated"
        mock_post.return_value = mock_response

        lead_data = {"name": "John Doe", "email": "john@example.com"}
        result = await self.tools.crm_update(lead_data)

        mock_post.assert_called_once_with(
            self.mock_env_vars["CRM_WEBHOOK_URL"],
            json=lead_data,
            headers=self.tools.headers, # Check if headers are passed
            timeout=15
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("Lead data successfully sent", result["message"])

    @patch('requests.post')
    async def test_crm_update_webhook_error(self, mock_post):
        """Test CRM update webhook error."""
        mock_response = MagicMock()
        mock_response.status_code = 400 # Client error
        mock_response.text = "Bad Request from CRM"
        mock_post.return_value = mock_response

        lead_data = {"name": "Jane Doe"}
        result = await self.tools.crm_update(lead_data)

        self.assertEqual(result["status"], "error")
        self.assertIn("CRM webhook returned an error", result["message"])
        self.assertIn("Status code: 400", result["message"])

    async def test_crm_update_no_webhook_url(self):
        """Test CRM update with no webhook URL set."""
        with patch.dict(os.environ, {"CRM_WEBHOOK_URL": ""}):
            tools_no_url = LeadQualificationTools()
            lead_data = {"name": "Test Lead"}
            result = await tools_no_url.crm_update(lead_data)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["message"], "CRM_WEBHOOK_URL is not set. Cannot send data to CRM.")

    # --- qualification_score Tests ---
    # This tool is pure Python logic, no external calls to mock here.

    async def test_qualification_score_pursue(self):
        """Test qualification_score resulting in 'pursue'."""
        profile_data = {
            "employee_count": 100, # In range
            "current_title": "VP of Engineering", # Budget keyword
            "summary_about_section": "We face scaling challenges and need to automate manual processes.", # Pain points
            "description": "" # Company description
        }
        # ICP config matching the LeadQualificationAgent's _get_icp_criteria
        icp_config = {
            "company_size_range": [10, 500], "company_size_weight": 0.30,
            "budget_authority_keywords": ["c-level", "vp", "director"], "budget_authority_weight": 0.25,
            "pain_point_keywords": ["manual process", "scaling challenge"], "pain_point_weight": 0.25,
            "engagement_min_summary_length": 50, "engagement_weight": 0.20,
            "pursue_threshold": 70, "nurture_threshold": 50
        }
        # Expected score: 30 (size) + 25 (budget) + 25 (pain) + 20 (engagement from summary) = 100
        
        result = await self.tools.qualification_score(profile_data, icp_config)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["recommendation"], "pursue")
        self.assertIn("Company size (100 employees) is within the ideal range", result["reasoning"])
        self.assertIn("suggests budget authority", result["reasoning"])
        self.assertIn("Keywords related to pain points found", result["reasoning"])
        self.assertIn("LinkedIn profile summary is present and detailed", result["reasoning"])


    async def test_qualification_score_nurture(self):
        """Test qualification_score resulting in 'nurture'."""
        profile_data = {
            "employee_count": 20, # In range
            "current_title": "Senior Manager", # Borderline/No clear budget keyword from default list
            "summary_about_section": "Looking to streamline operations.", # Pain point
            "description": "We are a growing company."
        }
        icp_config = {
            "company_size_range": [10, 500], "company_size_weight": 0.30,
            "budget_authority_keywords": ["c-level", "vp", "director", "chief", "head of"], "budget_authority_weight": 0.25,
            "pain_point_keywords": ["streamline", "scaling challenges"], "pain_point_weight": 0.25,
            "engagement_min_summary_length": 50, 
            "engagement_partial_summary_length_threshold":10, "engagement_weight": 0.20,
            "pursue_threshold": 70, "nurture_threshold": 50
        }
        # Expected score: 30 (size) + 0 (budget) + 25 (pain) + 10 (engagement, summary present but <50) = 65
        result = await self.tools.qualification_score(profile_data, icp_config)
        self.assertEqual(result["score"], 65) 
        self.assertEqual(result["recommendation"], "nurture")
        self.assertIn("Company size (20 employees) is within the ideal range", result["reasoning"])
        self.assertIn("does not clearly suggest budget authority", result["reasoning"])
        self.assertIn("Keywords related to pain points found", result["reasoning"])
        self.assertIn("LinkedIn profile summary is present but brief", result["reasoning"])


    async def test_qualification_score_disqualify(self):
        """Test qualification_score resulting in 'disqualify'."""
        profile_data = {
            "employee_count": 5, # Too small
            "current_title": "Intern", # No budget
            "summary_about_section": "", # No engagement, no pain points
            "description": "Just launched." 
        }
        icp_config = {
            "company_size_range": [10, 500], "company_size_weight": 0.30,
            "budget_authority_keywords": ["c-level", "vp", "director"], "budget_authority_weight": 0.25,
            "pain_point_keywords": ["manual process", "scaling challenge"], "pain_point_weight": 0.25,
            "engagement_min_summary_length": 50, 
            "engagement_partial_summary_length_threshold": 10, "engagement_weight": 0.20,
            "pursue_threshold": 70, "nurture_threshold": 50
        }
        # Expected score: 0 (size) + 0 (budget) + 0 (pain) + 0 (engagement) = 0
        result = await self.tools.qualification_score(profile_data, icp_config)
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["recommendation"], "disqualify")
        self.assertIn("Company size (5 employees) is outside the ideal range", result["reasoning"])
        self.assertIn("does not clearly suggest budget authority", result["reasoning"])
        self.assertIn("No clear keywords related to pain points found", result["reasoning"])
        self.assertIn("LinkedIn profile summary is missing or very short", result["reasoning"])

    async def test_qualification_score_missing_profile_data(self):
        """Test qualification_score with missing data points in profile."""
        profile_data = {
            "current_title": "CEO" # Only title, other fields missing
        }
        icp_config = {
            "company_size_range": [10, 500], "company_size_weight": 0.30,
            "budget_authority_keywords": ["ceo", "c-level", "vp", "director"], "budget_authority_weight": 0.25,
            "pain_point_keywords": ["manual process"], "pain_point_weight": 0.25,
            "engagement_min_summary_length": 50, "engagement_partial_summary_length_threshold": 10, "engagement_weight": 0.20,
            "pursue_threshold": 70, "nurture_threshold": 50
        }
        # Expected score: 0 (size) + 25 (budget) + 0 (pain) + 0 (engagement) = 25
        result = await self.tools.qualification_score(profile_data, icp_config)
        self.assertEqual(result["score"], 25)
        self.assertEqual(result["recommendation"], "disqualify")
        self.assertIn("Company size information is unavailable", result["reasoning"])
        self.assertIn("Title ('CEO') suggests budget authority", result["reasoning"])
        self.assertIn("No clear keywords related to pain points found", result["reasoning"])
        self.assertIn("LinkedIn profile summary is missing or very short", result["reasoning"])

# This allows running the tests directly from the script
if __name__ == '__main__':
    # unittest.main() would work if the script is run directly,
    # but for async tests, it's better to use an async-compatible runner
    # or manage the event loop explicitly if not using a test runner like pytest.
    # For simplicity with unittest, and since these are individual async tests:
    # Create a suite and run it.
    suite = unittest.TestSuite()
    # Need to use TestLoader to correctly load async tests if not using pytest
    # For direct unittest.main() or basic runner, you might need to wrap tests or use a compatible runner.
    # The tests are written as async def, which unittest's default runner might not handle directly without help.
    # However, many modern unittest integrations or specific runners (like pytest with pytest-asyncio) will.
    # For this environment, assuming a runner that handles `async def test_...` or manual execution:
    
    # A simple way to run all async tests in this class for this specific setup:
    loop = asyncio.get_event_loop()
    test_instance = TestLeadQualificationTools()
    
    # Discover all async test methods
    async_tests = [getattr(test_instance, method_name) for method_name in dir(test_instance)
                   if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(test_instance, method_name))]

    async def run_all():
        for test_method in async_tests:
            test_instance.setUp() # Call setUp before each test
            try:
                print(f"Running {test_method.__name__}...")
                await test_method()
                print(f"{test_method.__name__} PASSED")
            except AssertionError as e:
                print(f"{test_method.__name__} FAILED: {e}")
            finally:
                test_instance.tearDown() # Call tearDown after each test
    
    if not async_tests:
        print("No async tests found to run manually.")
    else:
        loop.run_until_complete(run_all())

    # If using pytest, simply run `pytest` in the terminal.
    # `unittest.main()` could be used if tests were synchronous or if using a special async test runner with unittest.
    # For now, this manual loop provides a way to execute them if pytest is not the primary runner.
    # Consider using `pytest` and `pytest-asyncio` for a more robust solution.
    # To make it runnable with `python -m unittest tests/test_lead_qualification_tools.py`,
    # each async test method would need to be wrapped, e.g. `def test_x(self): asyncio.run(self._test_x_async())`
    # For now, the above loop is a direct way to execute if not using pytest.
    # If this needs to be strictly unittest runnable without external runners, test methods should be sync and use asyncio.run internally.
    # Given the project structure, `pytest` is more likely.
    # The instructions mention `asyncio.run`, implying it's okay to manage the loop or use an async runner.
    print("\nNote: For comprehensive test discovery and execution, consider using 'pytest' with 'pytest-asyncio'.")
