from swarms import SequentialWorkflow
from backend.agents.lead_qualification.agent import LeadQualificationAgent
from backend.providers.multi_provider import MultiProvider

class LeadQualificationWorkflow(SequentialWorkflow):
    def __init__(self, multi_provider: MultiProvider):
        self.lead_qualification_agent = LeadQualificationAgent(multi_provider=multi_provider)
        # Pass the agent as a list to the superclass constructor
        super().__init__(agents=[self.lead_qualification_agent])

    def run(self, lead_data: dict):
        """
        Runs the lead qualification workflow.
        """
        print("LeadQualificationWorkflow is running...")
        # The SequentialWorkflow will automatically pass the output of one step
        # as the input to the next. In this simple case, the lead_data
        # is passed to the LeadQualificationAgent's run method.
        workflow_result = super().run(lead_data)
        print(f"Workflow run result: {workflow_result}")
        return workflow_result

if __name__ == "__main__":
    # Example usage (for testing purposes)
    from dotenv import load_dotenv
    import os

    load_dotenv()

    # Assuming MultiProvider can be initialized without complex setup for this basic test
    # In a real scenario, this would involve proper configuration and potential async
    # For now, we'll use a placeholder or simplified MultiProvider if available
    # Replace with actual MultiProvider initialization if possible
    class MockMultiProvider:
        def complete(self, prompt, max_tokens=100):
            print(f"MockMultiProvider received prompt: {prompt}")
            return "Mock completion response."

    # Check if actual MultiProvider can be initialized
    try:
        # Attempt to initialize the real MultiProvider
        # This might require more setup, so wrap in try-except
        real_multi_provider = MultiProvider()
        provider_instance = real_multi_provider
        print("Using real MultiProvider")
    except Exception as e:
        print(f"Could not initialize real MultiProvider: {e}")
        print("Using MockMultiProvider")
        provider_instance = MockMultiProvider()

    workflow = LeadQualificationWorkflow(multi_provider=provider_instance)

    sample_lead_data = {
        "name": "Jane Doe",
        "company": "Another Corp",
        "title": "Sales Representative",
        "email": "jane.doe@anothercorp.com",
        "linkedin": "linkedin.com/in/janedoe"
    }

    workflow_output = workflow.run(sample_lead_data)
    print(f"Final workflow output: {workflow_output}")
