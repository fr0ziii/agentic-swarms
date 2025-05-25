import asyncio
import json
from typing import Dict

# Assuming these are correctly importable from your project structure
from swarms import Agent 
from backend.providers.multi_provider import MultiProvider
from backend.database.supabase_client import SupabaseClient
from .tools import LeadQualificationTools

class LeadQualificationAgent(Agent):
    def __init__(self, multi_provider: MultiProvider, supabase_client: SupabaseClient):
        super().__init__()
        self.name = "lead_qualification_agent"
        self.provider = multi_provider
        self.db = supabase_client
        self.tools = LeadQualificationTools()
        self.system_prompt = self._load_system_prompt()
        # self.history will be inherited from Agent or should be initialized if not

    def _get_icp_criteria(self) -> dict:
        """
        Returns the Ideal Customer Profile (ICP) criteria as a structured dictionary.
        This configuration is used by the qualification_score tool.
        """
        return {
            "company_size_range": [10, 500],  # Min and Max employee count
            "company_size_weight": 0.30,
            "budget_authority_keywords": [
                "c-level", "vp", "director", "vice president", 
                "chief officer", "head of", "founder", "partner", "owner", "president"
            ],  # Lowercased in tool
            "budget_authority_weight": 0.25,
            "pain_point_keywords": [
                "manual process", "manual processes", "scaling challenge", "scaling challenges", 
                "inefficient", "streamline", "automate", "bottleneck", "optimize workflow", 
                "integration issue", "data silos", "legacy system", "technical debt", 
                "improve productivity", "reduce overhead"
            ],  # Lowercased in tool
            "pain_point_weight": 0.25,
            "engagement_min_summary_length": 50,  # For LinkedIn summary as a proxy
            # Threshold for a partial score if summary is very short but present
            "engagement_partial_summary_length_threshold": 10, 
            "engagement_weight": 0.20,
            "pursue_threshold": 70, 
            "nurture_threshold": 50  
        }

    def _load_system_prompt(self) -> str:
        # Updated to reflect that qualification_score is internal and tool descriptions are more detailed.
        # Also, QUALIFICATION CRITERIA description is updated.
        return """
        You are a Lead Qualification Agent for B2B SaaS companies.

        ROLE: Expert sales development representative with 10+ years qualifying enterprise leads. Your task is to analyze provided lead data, extract key information, and suggest how to approach the lead. A system tool will calculate the final qualification score and recommendation based on the data you help process.

        TOOLS AVAILABLE (These are used by the system to gather data *before* your analysis. You do not call them.):
        - linkedin_profile_scraper(url: string): Extracts detailed information from a LinkedIn profile, including name, current title, current company, location, summary/about section, work experience, education, and skills.
        - company_research(domain: string): Researches company information given a domain. Provides company name, description, location, estimated employee count, and industry.
        - crm_update(lead_data: object): (For system use later) Sends the final lead data (including score and recommendation) to a configured CRM webhook. You should not request this tool.

        QUALIFICATION CRITERIA (These are used by an internal system tool to score the lead after your analysis. Your role is to gather and highlight data that helps this tool work effectively.):
        - Company Size: Target is 10-500 employees. (Weight: 30%)
        - Budget Authority: The person's title should suggest decision-making power (e.g., C-level, VP, Director, Head of, Founder). (Weight: 25%)
        - Pain Points: The person's LinkedIn summary or the company's description should mention keywords related to challenges our solution addresses (e.g., "manual process," "scaling challenge," "inefficient," "automate"). (Weight: 25%)
        - Engagement Level: Assessed as a proxy by the presence and length of the person's LinkedIn summary. A detailed summary (e.g., >50 characters) suggests higher engagement. (Weight: 20%)

        PROCESS:
        1. OBSERVE: You will be provided with pre-gathered data from LinkedIn and company research tools.
        2. THINK: Analyze this data. Your main goal is to extract qualitative insights, identify compelling personalization hooks for outreach, and suggest a logical next action.
        3. REASON: Explain your reasoning for the suggested personalization hooks and next action based on the observed data.
        4. DECIDE: Propose a `next_action`. Your `observation`, `reasoning` (for hooks and next action), `personalization_hooks`, and `confidence` are key outputs.
        (The system will then calculate a precise qualification score and recommendation using an internal tool based on the data and the above criteria, and combine it with your qualitative analysis.)

        RESPONSE FORMAT (Your response should strictly follow this JSON structure. The `score` and `recommendation` fields you provide will be considered preliminary and may be updated by the system's scoring tool.):
        {
            "observation": "Concise summary of key qualitative observations about the lead and company, focusing on aspects relevant for personalization and engagement, beyond simple keyword matching.",
            "reasoning": "Your reasoning for the suggested personalization_hooks and next_action based on your observation of the lead's profile and company data.",
            "score": 0, 
            "recommendation": "", 
            "next_action": "Specific next step to take (e.g., 'Send personalized email referencing their work on X', 'Suggest a brief call to discuss Y')",
            "personalization_hooks": ["Specific detail from their profile for outreach", "Another specific detail or talking point"],
            "confidence": 0.85,
            "tools_used": []
        }

        QUALITY STANDARDS:
        - Focus on providing actionable `personalization_hooks` and a well-justified `next_action`.
        - Your `observation` should highlight nuances not easily captured by automated scoring.
        - Do not attempt to calculate the final score or make the final recommendation; the system tool handles this.
        """

    async def qualify_lead(self, linkedin_url: str, company_domain: str = None) -> Dict:
        """Main qualification method"""
        llm_response_json: Dict = {} 
        profile_data: Dict = {"profile_url": linkedin_url}
        if company_domain:
            profile_data["domain"] = company_domain

        try:
            # Step 1: Gather lead data using tools (System step)
            linkedin_data = await self.tools.linkedin_profile_scraper(linkedin_url)
            if linkedin_data.get("error"):
                print(f"Error scraping LinkedIn: {linkedin_data.get('error')}")
                profile_data["linkedin_error"] = linkedin_data.get("error")
            else:
                profile_data.update(linkedin_data)

            if company_domain:
                company_data = await self.tools.company_research(company_domain)
                if company_data.get("error"):
                    print(f"Error researching company: {company_data.get('error')}")
                    profile_data["company_research_error"] = company_data.get("error")
                else:
                    profile_data.update(company_data)
            
            profile_data["lead_name"] = linkedin_data.get("name", "N/A")
            profile_data["company_name"] = company_data.get("company_name") if company_domain and company_data and company_data.get("company_name") not in [None, "N/A"] else linkedin_data.get("current_company", "N/A")

            # Step 2: Process with LLM for qualitative analysis
            prompt = f"{self.system_prompt}\n\nLEAD DATA (Collected by system tools):\n{json.dumps(profile_data, indent=2)}\n\nTask: Based on the system prompt and the provided lead data, perform your qualitative analysis and provide your response in the specified JSON format. Focus on `observation`, `reasoning` (for hooks and next action), `personalization_hooks`, `next_action`, and `confidence`."

            llm_response_obj = await self.provider.complete(
                prompt=prompt,
                provider="openai", 
                temperature=0.1,
                max_tokens=1000 
            )
            llm_response_json = json.loads(llm_response_obj.content)

            # Step 3: System calculates qualification score
            icp_criteria_config = self._get_icp_criteria()
            score_result = await self.tools.qualification_score(profile=profile_data, icp_config=icp_criteria_config)

            # Step 4: Merge LLM response with system's score_result
            final_result = {
                "lead_name": profile_data.get("lead_name", "N/A"),
                "company_name": profile_data.get("company_name", "N/A"),
                "profile_url": linkedin_url,
                "domain": company_domain if company_domain else profile_data.get("domain", "N/A"),
                "observation": llm_response_json.get("observation", "No specific observations from LLM."),
                "score": score_result.get("score"), 
                "recommendation": score_result.get("recommendation"),
                "reasoning": f"LLM Qualitative Analysis: {llm_response_json.get('reasoning', 'N/A')}. System Score Calculation: {score_result.get('reasoning', 'N/A')}",
                "next_action": llm_response_json.get("next_action", "Review manually"),
                "personalization_hooks": llm_response_json.get("personalization_hooks", []),
                "confidence": llm_response_json.get("confidence", 0.5), 
                "tools_used_by_system": ["linkedin_profile_scraper", "company_research", "qualification_score_internal"],
                "raw_profile_data_summary": { # Avoid dumping extremely large raw data if not needed
                    "linkedin_summary_present": bool(profile_data.get("summary_about_section")),
                    "company_description_present": bool(profile_data.get("description")),
                    "employee_count": profile_data.get("employee_count"),
                    "lead_title": profile_data.get("current_title")
                }
            }
            
            # Step 5: Store in memory
            await self._store_qualification_result(linkedin_url, final_result)

            # Step 6: Update CRM (conditionally)
            if final_result["recommendation"] in ["pursue", "nurture"]:
                crm_status = await self.tools.crm_update(final_result) # Send final_result
                final_result["crm_update_status"] = crm_status
            
            # self.history.append({"role": "assistant", "content": json.dumps(final_result)}) # If Agent class handles history
            return final_result

        except Exception as e:
            print(f"Error in qualify_lead: {type(e).__name__} - {e}")
            await self._handle_error(e, linkedin_url)
            return {
                "error": f"{type(e).__name__}: {str(e)}", 
                "score": 0, 
                "recommendation": "disqualify",
                "reasoning": f"An error occurred: {type(e).__name__} - {str(e)}",
                "profile_data_collected_summary": {
                    "linkedin_profile_url": linkedin_url,
                    "company_domain": company_domain,
                    "linkedin_data_retrieved": "error" if "linkedin_error" in profile_data else ("partial" if not linkedin_data.get("name") else "retrieved"),
                    "company_data_retrieved": "error" if "company_research_error" in profile_data else ("partial" if not company_data.get("company_name") else "retrieved"),
                },
                "llm_response_attempted": llm_response_json if llm_response_json else "LLM call not reached or failed."
            }

    async def _store_qualification_result(self, linkedin_url: str, result: Dict):
        """Store result in vector database for future reference"""
        content_summary = (
            f"Lead: {result.get('lead_name', 'N/A')} at {result.get('company_name', 'N/A')}. "
            f"Score: {result.get('score', 'N/A')}, Recommendation: {result.get('recommendation', 'N/A')}. "
            f"Observation: {result.get('observation', 'N/A')}"
        )
        
        metadata_to_store = {
            "linkedin_url": linkedin_url,
            "company_domain": result.get('domain', 'N/A'),
            "score": result.get('score'),
            "recommendation": result.get('recommendation'),
            "llm_confidence": result.get('confidence'),
            "next_action": result.get('next_action')
        }
        metadata_to_store = {k: v for k, v in metadata_to_store.items() if v is not None}

        try:
            await self.db.store_memory(
                agent_id=self.name,
                content=content_summary,
                metadata=metadata_to_store
            )
        except Exception as db_error:
            print(f"Failed to store result in DB: {db_error}")


    async def _handle_error(self, error: Exception, context: str):
        error_message = f"Error in LeadQualificationAgent: {type(error).__name__} - {error} - Context: {context}"
        print(error_message)
        try:
            await self.db.store_memory(
                agent_id=f"{self.name}_errors",
                content=error_message,
                metadata={"context": context, "error_type": type(error).__name__}
            )
        except Exception as db_error:
            print(f"Additionally, failed to store error in DB: {db_error}")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    
    # Ensure critical env vars are at least nominally set for tools to init
    os.environ.setdefault('LINKEDIN_SCRAPER_API_KEY', 'dummy_linkedin_key_for_init')
    os.environ.setdefault('HUNTER_API_KEY', 'dummy_hunter_key_for_init')
    os.environ.setdefault('CRM_WEBHOOK_URL', 'https://example.com/webhook_for_init')

    class MockMultiProvider:
        async def complete(self, prompt, provider=None, temperature=None, max_tokens=None, functions=None):
            print(f"MockMultiProvider received prompt for {provider} (first 150 chars): {prompt[:150]}...")
            llm_simulated_response = {
                "observation": "Mock LLM: Lead's summary shows 'driving growth' and company focuses on 'cloud solutions'.",
                "reasoning": "Mock LLM: 'Driving growth' aligns with efficiency needs. 'Cloud solutions' is our target market.",
                "score": 0, "recommendation": "", # Placeholders
                "next_action": "Send email about cloud efficiency case study.",
                "personalization_hooks": ["Mention their 'driving growth' phrase.", "Connect to 'cloud solutions' focus."],
                "confidence": 0.90,
                "tools_used": [] 
            }
            # Simulate the structure of the provider's response object
            class MockProviderResponse:
                def __init__(self, content_dict):
                    self.content = json.dumps(content_dict)
                    self.usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
            return MockProviderResponse(llm_simulated_response)

    class MockSupabaseClient:
        async def store_memory(self, agent_id, content, metadata):
            print(f"MockSupabaseClient: Storing for {agent_id}, Content: '{content[:60]}...', Metadata: {metadata}")
            pass

    provider_instance = MockMultiProvider()
    db_instance = MockSupabaseClient()
    
    agent = LeadQualificationAgent(multi_provider=provider_instance, supabase_client=db_instance)

    # --- Mocking agent's tools for controlled testing ---
    original_linkedin_scraper = agent.tools.linkedin_profile_scraper
    original_company_research = agent.tools.company_research
    original_crm_update = agent.tools.crm_update
    # qualification_score is part of tools, its logic is tested there, here we test agent's use of it.

    async def mock_linkedin_scraper_main(url):
        print(f"MAIN TEST MOCK linkedin_profile_scraper for {url}")
        if "satyanadella" in url:
            return {
                "name": "Satya Nadella (Mocked)", "current_title": "Chairman and Chief Executive Officer",
                "current_company": "Microsoft (LinkedIn)", 
                "location": "Redmond, WA", "summary_about_section": "AI, cloud, digital transformation. Scaling solutions, automating processes. (Mocked)",
                "work_experience": [{"title": "CEO", "company": "Microsoft"}], "education": [{"institution": "UChicago"}], "skills": ["AI", "Cloud"]
            }
        elif "janedoe-intern" in url:
             return {
                "name": "Jane Doe (Mocked Intern)", "current_title": "Intern", 
                "current_company": "Small Startup (LinkedIn)", "location": "CA, USA",
                "summary_about_section": "Learning new things.", "skills": ["Python"], "work_experience": [], "education": []
            }
        return {"error": "Mocked LinkedIn profile not found in main test for " + url}

    async def mock_company_research_main(domain):
        print(f"MAIN TEST MOCK company_research for {domain}")
        if "microsoft.com" in domain:
            return {
                "company_name": "Microsoft Corp (Company Research)", "description": "Enables digital transformation. Streamline enterprise workflows.",
                "location": "Redmond, USA", "employee_count": 220000, # Deliberately outside ICP
                "industry": "Software Development"
            }
        elif "smallstartup.xyz" in domain:
            return {
                "company_name": "Small Startup Inc (Company Research)", "description": "A new company.",
                "location": "CA, USA", "employee_count": 5, # Too small
                "industry": "Tech"
            }
        return {"error": "Mocked company data not found in main test for " + domain}
    
    async def mock_crm_update_main(data):
        print(f"MAIN TEST MOCK crm_update for: {data.get('lead_name')}, Recommendation: {data.get('recommendation')}")
        return {"status": "success", "message": "Mocked CRM update successful."}

    agent.tools.linkedin_profile_scraper = mock_linkedin_scraper_main
    agent.tools.company_research = mock_company_research_main
    agent.tools.crm_update = mock_crm_update_main
    # --- End of Tool Mocking ---

    async def run_test_case(linkedin_url, company_domain, test_name):
        print(f"\n--- Test Case: {test_name} ---")
        print(f"Input - LinkedIn URL: {linkedin_url}, Company Domain: {company_domain}")
        result = await agent.qualify_lead(linkedin_url, company_domain)
        print(f"\nFinal Result for {test_name}:")
        print(json.dumps(result, indent=2))
        assert "error" not in result or result["error"] is None, f"Test case {test_name} failed with an error in result."
        assert "score" in result, f"Score missing in result for {test_name}"
        assert "recommendation" in result, f"Recommendation missing for {test_name}"

    async def run_all_tests():
        await run_test_case("https://www.linkedin.com/in/satyanadella/", "microsoft.com", "Satya Nadella (Microsoft)")
        await run_test_case("https://www.linkedin.com/in/janedoe-intern/", "smallstartup.xyz", "Jane Doe (Small Startup)")
        
        # Restore original tools after tests if needed by other parts of application
        agent.tools.linkedin_profile_scraper = original_linkedin_scraper
        agent.tools.company_research = original_company_research
        agent.tools.crm_update = original_crm_update

    asyncio.run(run_all_tests())
