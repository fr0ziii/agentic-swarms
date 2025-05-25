# Lead Qualification Agent

## Overview

The Lead Qualification Agent is an AI-powered system designed to automate the process of qualifying B2B SaaS leads. It gathers information about potential leads and their companies from various sources, scores them against an Ideal Customer Profile (ICP), and provides recommendations for next actions. The agent aims to streamline the top-of-funnel sales development process, allowing sales teams to focus on the most promising prospects.

## Features

-   **LinkedIn Profile Scraping**: Extracts detailed information from a lead's LinkedIn profile (e.g., name, title, company, summary, experience, education, skills).
-   **Company Research**: Gathers company-specific data (e.g., name, description, location, employee count, industry) based on the company's domain.
-   **Automated Scoring**: Calculates a qualification score for each lead based on predefined Ideal Customer Profile (ICP) criteria, including company size, budget authority, identified pain points, and engagement level.
-   **CRM Integration**: Sends qualified lead data to a generic CRM webhook for further processing and tracking.
-   **Configurable ICP**: The Ideal Customer Profile criteria (weights, keywords, thresholds) are configurable within the agent via the `_get_icp_criteria()` method.
-   **LLM-Powered Analysis**: Leverages a Large Language Model (LLM) for qualitative analysis, generating observations, personalization hooks, and suggesting next actions.

## Configuration

The Lead Qualification Agent relies on several environment variables for its operation. These should be set in your environment or in a `.env` file at the root of the project.

### Required Environment Variables:

1.  **`LINKEDIN_SCRAPER_API_KEY`**:
    *   **Purpose**: API key for the LinkedIn scraping service (currently configured for BrightData).
    *   **Where to get it**: Sign up for a BrightData account and obtain an API key from their dashboard. Look for their "Web Scraper API" or "Datasets for LinkedIn".
    *   **Note**: The current integration with BrightData in `tools.py` simulates a synchronous response after triggering an asynchronous job. A production-ready implementation would require handling BrightData's asynchronous webhook/callback mechanism to retrieve the actual scraped data. This is documented in the `linkedin_profile_scraper` tool's docstring.

2.  **`HUNTER_API_KEY`**:
    *   **Purpose**: API key for Hunter.io, used for company research (enrichment based on domain).
    *   **Where to get it**: Sign up for a Hunter.io account. API keys are available in your account dashboard. They offer a free plan that usually includes API access.

3.  **`CRM_WEBHOOK_URL`**:
    *   **Purpose**: The URL of your generic CRM webhook endpoint. The agent will POST lead data (including score and recommendation) to this URL.
    *   **How to set it**: This is user-provided. You need to set up a webhook receiver (e.g., using Zapier, Pipedream, or a custom endpoint on your CRM) that can accept a JSON payload with the lead data. The structure of this payload can be seen in the `crm_update` tool and the final output of the `qualify_lead` method.

4.  **`OPENAI_API_KEY`**:
    *   **Purpose**: Required by `MultiProvider` if OpenAI is the chosen LLM provider for qualitative analysis. This is a general requirement for the broader system if OpenAI is used.
    *   **Where to get it**: From your OpenAI account dashboard.
    *   **Note**: If using other LLMs via `MultiProvider` (e.g., Anthropic), their respective API keys would be needed (e.g., `ANTHROPIC_API_KEY`). These should be configured as per the `MultiProvider`'s requirements.

5.  **`SUPABASE_URL`** and **`SUPABASE_KEY`**:
    *   **Purpose**: Credentials for the Supabase client, used for storing lead qualification results and error logs. This is a general requirement for the broader system.
    *   **Where to get them**: From your Supabase project dashboard (Settings > API).

### Example `.env` file:

```env
# Lead Qualification Agent Configuration
LINKEDIN_SCRAPER_API_KEY="your_brightdata_api_key"
HUNTER_API_KEY="your_hunter_io_api_key"
CRM_WEBHOOK_URL="https_your_crm_webhook_url_com/endpoint"

# General System Configuration (ensure these are set for the application)
OPENAI_API_KEY="your_openai_api_key"
# ANTHROPIC_API_KEY="your_anthropic_api_key" # If using Anthropic

# Supabase Configuration
SUPABASE_URL="https://your-project-id.supabase.co"
SUPABASE_KEY="your_supabase_anon_key"
```

## How to Use

The agent is primarily used through its `qualify_lead` method.

### Initialization:

First, ensure you have `MultiProvider` and `SupabaseClient` instances initialized with appropriate API keys set in the environment.

```python
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv() 

from backend.providers.multi_provider import MultiProvider
from backend.database.supabase_client import SupabaseClient
from backend.agents.lead_qualification.agent import LeadQualificationAgent

# Initialize dependencies 
# Ensure API keys for providers (OpenAI, etc.) are set in your environment
multi_provider = MultiProvider() # Assumes OPENAI_API_KEY is set if OpenAI is default
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not (supabase_url and supabase_key):
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
supabase_client = SupabaseClient(supabase_url, supabase_key)

# Instantiate the agent
lead_qual_agent = LeadQualificationAgent(
    multi_provider=multi_provider,
    supabase_client=supabase_client
)
```

### Qualifying a Lead:

Call the `qualify_lead` method with the lead's LinkedIn URL and optionally their company domain.

```python
# (Continued from initialization example)
async def main_qualify():
    linkedin_url = "https://www.linkedin.com/in/someleadprofile/" # Replace with actual URL
    company_domain = "examplecompany.com" # Replace with actual domain or omit

    qualification_result = await lead_qual_agent.qualify_lead(
        linkedin_url=linkedin_url,
        company_domain=company_domain
    )
    print(json.dumps(qualification_result, indent=2))

if __name__ == "__main__":
    # This example assumes the script is run where it can find the backend modules
    # and that environment variables are loaded.
    # Example: python -m backend.agents.lead_qualification.agent 
    # (if __main__ block in agent.py is adapted for direct execution with example URLs)
    # For this README example, we'll just show the conceptual main_qualify call.
    # To run the example from agent.py, you would typically execute that file directly.
    # asyncio.run(main_qualify()) # This would be part of your application logic
    pass
```

The agent will perform data gathering, LLM analysis, and scoring, returning a JSON-like dictionary. The structure of this dictionary is defined by the `final_result` in the `qualify_lead` method of `agent.py`.

## Tool Details

The agent utilizes several tools (defined in `tools.py`) to gather and process information:

-   **`linkedin_profile_scraper(url: str)`**:
    -   **Purpose**: Fetches data from a LinkedIn profile URL.
    -   **Implementation Note**: Currently uses BrightData's API. The integration simulates a synchronous response for demonstration. A production setup would need to handle BrightData's asynchronous job completion (e.g., via webhooks), as noted in the tool's docstring.
    -   **Data Points**: Name, current title, current company, location, summary/about section, work experience, education, skills.

-   **`company_research(domain: str)`**:
    -   **Purpose**: Retrieves company information based on its domain.
    -   **Implementation Note**: Uses the Hunter.io API.
    -   **Data Points**: Company name, description, location, estimated employee count, industry.

-   **`qualification_score(profile: dict, icp_config: dict)`**:
    -   **Purpose**: Calculates a numerical score (0-100) based on the aggregated `profile` data and a structured `icp_config`. This tool is called internally by the agent system.
    -   **Implementation Note**:
        -   Pain point detection is keyword-based, searching in the LinkedIn summary and company description. This is a simplification and might require more advanced NLP for higher accuracy.
        -   Engagement level is a proxy based on the presence and length of the LinkedIn summary. This is also a simplification.
        -   The ICP criteria (keywords, weights, thresholds for scoring) are defined in the `LeadQualificationAgent._get_icp_criteria()` method.

-   **`crm_update(lead_data: dict)`**:
    -   **Purpose**: Sends the final lead qualification data (including score, recommendation, etc.) to a generic webhook URL specified by the `CRM_WEBHOOK_URL` environment variable.
    -   **Implementation Note**: The receiving webhook is responsible for mapping the received JSON data to the specific CRM's fields.

For detailed implementation of these tools, refer to `backend/agents/lead_qualification/tools.py`.
For the agent's logic and ICP configuration, refer to `backend/agents/lead_qualification/agent.py`.

## Testing

Unit tests are provided in the `tests/` directory:
- `tests/test_lead_qualification_tools.py`
- `tests/test_lead_qualification_agent.py`

To run the tests, ensure you have `pytest` and `pytest-asyncio` installed (they are listed in `requirements.txt`). Navigate to the project root and run:
```bash
pytest
```
This will discover and execute the tests.
```
