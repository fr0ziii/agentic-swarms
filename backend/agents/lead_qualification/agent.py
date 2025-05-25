from swarms import Agent
from typing import Dict, List, Optional
import json
from backend.providers.multi_provider import MultiProvider
from backend.database.supabase_client import SupabaseClient
from .tools import LeadQualificationTools # Import the tools

class LeadQualificationAgent(Agent):
    def __init__(self, multi_provider: MultiProvider, supabase_client: SupabaseClient):
        super().__init__()
        self.name = "lead_qualification_agent"
        self.provider = multi_provider
        self.db = supabase_client
        self.tools = LeadQualificationTools() # Initialize the tools
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        return """
        You are a Lead Qualification Agent for B2B SaaS companies.

        ROLE: Expert sales development representative with 10+ years qualifying enterprise leads

        TOOLS AVAILABLE:
        - linkedin_profile_scraper(url: string)
        - company_research(domain: string)
        - crm_update(lead_data: object)
        - qualification_score(profile: object, icp: object)

        QUALIFICATION CRITERIA:
        - Company Size: 10-500 employees (weight: 30%)
        - Budget Authority: C-level, VP, Director roles (weight: 25%)
        - Pain Points: Manual processes, scaling challenges (weight: 25%)
        - Engagement Level: Active on LinkedIn, posts about challenges (weight: 20%)

        PROCESS:
        1. OBSERVE: Analyze provided LinkedIn profile URL
        2. THINK: Determine which additional data points needed
        3. ACT: Use appropriate tools to gather information
        4. REASON: Calculate qualification score using weighted criteria
        5. DECIDE: Recommend next action (pursue, nurture, disqualify)

        RESPONSE FORMAT:
        Always respond in this JSON structure:
        {
            "observation": "What I see in the lead profile",
            "reasoning": "Step-by-step analysis process",
            "score": 85,
            "recommendation": "pursue|nurture|disqualify",
            "next_action": "Specific next step to take",
            "personalization_hooks": ["specific details for outreach"],
            "confidence": 0.92
        }

        QUALITY STANDARDS:
        - Never qualify leads below 70 score as "pursue"
        - Always provide specific reasoning for scores
        - Include 2-3 personalization hooks for outreach
        - Update CRM with all collected data points
        """

    async def qualify_lead(self, linkedin_url: str, company_domain: str = None) -> Dict:
        """Main qualification method"""
        try:
            # Step 1: Gather lead data using tools
            profile_data = await self.tools.linkedin_profile_scraper(linkedin_url)

            if company_domain:
                company_data = await self.tools.company_research(company_domain)
                profile_data.update(company_data)

            # Step 2: Process with LLM using MultiProvider
            prompt = f"{self.system_prompt}\n\nLEAD DATA: {json.dumps(profile_data)}"

            response = await self.provider.complete(
                prompt=prompt,
                provider="openai",  # Primary for complex analysis
                temperature=0.1,
                max_tokens=1000
            )

            # Step 3: Parse and validate response
            result = json.loads(response.content)

            # Step 4: Store in memory using SupabaseClient
            await self._store_qualification_result(linkedin_url, result)

            # Step 5: Update CRM using tools
            await self.tools.crm_update(result)

            return result

        except Exception as e:
            await self._handle_error(e, linkedin_url)
            return {"error": str(e), "score": 0, "recommendation": "disqualify"}

    async def _store_qualification_result(self, linkedin_url: str, result: Dict):
        """Store result in vector database for future reference"""
        content = f"Lead qualification: {result['observation']} Score: {result['score']}"
        await self.db.store_memory(
            agent_id=self.name,
            content=content,
            metadata={
                "linkedin_url": linkedin_url,
                "score": result['score'],
                "recommendation": result['recommendation']
            }
        )

    async def _handle_error(self, error: Exception, context: str):
        """Error handling and logging"""
        print(f"Error in LeadQualificationAgent: {error} - Context: {context}")
        # Implement proper logging and error reporting

if __name__ == "__main__":
    # Example usage (for testing purposes)
    # This part will likely be removed or modified when integrated into workflows
    from dotenv import load_dotenv
    import os

    load_dotenv()

    # Assuming MultiProvider and SupabaseClient can be initialized for this basic test
    # In a real scenario, this would involve proper configuration and potential async
    # For now, we'll use placeholders or simplified versions if available
    class MockMultiProvider:
        async def complete(self, prompt, max_tokens=100, provider=None, temperature=None, functions=None):
            print(f"MockMultiProvider received prompt: {prompt[:50]}...")
            return {"content": '{"observation": "Mock observation", "reasoning": "Mock reasoning", "score": 75, "recommendation": "pursue", "next_action": "Mock next action", "personalization_hooks": ["hook1", "hook2"], "confidence": 0.8}', "usage": {}}

    class MockSupabaseClient:
        async def store_memory(self, agent_id, content, metadata):
            print(f"MockSupabaseClient storing memory for {agent_id}: {content[:50]}...")
            pass

    # Check if actual MultiProvider and SupabaseClient can be initialized
    try:
        # Attempt to initialize the real MultiProvider and SupabaseClient
        real_multi_provider = MultiProvider()
        real_supabase_client = SupabaseClient()
        provider_instance = real_multi_provider
        db_instance = real_supabase_client
        print("Using real MultiProvider and SupabaseClient")
    except Exception as e:
        print(f"Could not initialize real MultiProvider or SupabaseClient: {e}")
        print("Using MockMultiProvider and MockSupabaseClient")
        provider_instance = MockMultiProvider()
        db_instance = MockSupabaseClient()


    agent = LeadQualificationAgent(multi_provider=provider_instance, supabase_client=db_instance)

    sample_linkedin_url = "https://www.linkedin.com/in/johndoe"
    sample_company_domain = "example.com"

    # Note: The tools (linkedin_profile_scraper, company_research, crm_update, qualification_score)
    # within the agent's qualify_lead method are still placeholders in tools.py.
    # This test will simulate calling those placeholders.

    result = asyncio.run(agent.qualify_lead(sample_linkedin_url, sample_company_domain))
    print(f"Agent qualify_lead result: {result}")
