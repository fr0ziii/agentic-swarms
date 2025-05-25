import os # For os.getenv
import json # For json.JSONDecodeError
from typing import Dict, Optional
import requests
from bs4 import BeautifulSoup # Used by old _extract methods
import re # Used by old _extract methods

class LeadQualificationTools:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/json' # Default content type for POST requests
        }
        self.linkedin_api_key = os.getenv("LINKEDIN_SCRAPER_API_KEY")
        self.hunter_api_key = os.getenv("HUNTER_API_KEY")
        self.crm_webhook_url = os.getenv("CRM_WEBHOOK_URL")

        if not self.crm_webhook_url:
            print("Warning: CRM_WEBHOOK_URL environment variable is not set. CRM updates will fail.")
        if not self.linkedin_api_key:
            print("Warning: LINKEDIN_SCRAPER_API_KEY environment variable is not set. LinkedIn scraping will fail.")
        if not self.hunter_api_key:
            print("Warning: HUNTER_API_KEY environment variable is not set. Company research will fail.")

    async def linkedin_profile_scraper(self, url: str) -> Dict:
        """
        Scrape LinkedIn profile data using BrightData's Web Scraper API.
        Note: BrightData's API for LinkedIn profiles is typically asynchronous (trigger-based).
        This implementation simulates a synchronous call for demonstration purposes and
        returns a structured dictionary with placeholders for data not explicitly available
        in the basic BrightData example response. A production system would need to handle
        the asynchronous nature (e.g., webhooks, polling).

        Required data points:
        - name, current title, current company, location, summary/about section,
        - work experience (list of positions with company, title, dates),
        - education (list of institutions with degree, field of study, dates),
        - skills.
        """
        if not self.linkedin_api_key:
            return {"error": "LINKEDIN_SCRAPER_API_KEY not found in environment variables."}

        # BrightData API endpoint for triggering LinkedIn profile scrapes
        # This specific dataset_id is from their public documentation for generic profile scraping
        api_url = "https://api.brightdata.com/datasets/v3/trigger?dataset_id=gd_l1viktl72bvl7bjuj0&format=json&uncompressed_webhook=true"
        
        headers = {
            "Authorization": f"Bearer {self.linkedin_api_key}",
            "Content-Type": "application/json"
        }
        
        # The API expects a list of URLs
        payload = [{"url": url}]

        try:
            # This call triggers the scrape. For a real async setup, we'd get a job ID.
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status() # Raise an exception for bad status codes
            
            # BrightData's trigger API usually returns a response indicating the job has started,
            # not the actual data. For example: {'collection_id': 'some_id', ...}
            # The actual data would be delivered later (e.g., webhook, S3).
            
            # SIMULATION: Since we can't get live data synchronously here,
            # we'll simulate a response structure based on the provided example
            # and the required fields.
            # In a real scenario, you would fetch the data from the delivery location
            # using the collection_id or a webhook mechanism.

            # The example output from BrightData is very basic:
            # { "id": "...", "name": "...", "city": "...", "country_code": "...", 
            #   "position": "...", "about": null }
            # We need to map this and add placeholders for other required fields.

            # Let's assume a hypothetical successful synchronous response for simulation:
            # For this example, we'll use the input URL in the simulation, as the API doesn't return it directly.
            
            # Placeholder for actual data extraction logic from BrightData's response
            # If BrightData had a synchronous API, the result might look like this:
            # brightdata_result = response.json() 
            # For now, we simulate.
            
            # Simulated data based on a hypothetical full profile from BrightData
            # This structure aims to fulfill the requirements.
            simulated_profile_data = {
                "name": "Daniece M****s (Simulated)", # From example
                "current_title": "Library Media Specialist", # Derived from "position"
                "current_company": "Greeneville City Schools, Greeneville High School", # Derived from "position"
                "location": "Greeneville, Tennessee, United States", # From "city"
                "summary_about_section": "Simulated summary: Passionate educator and media specialist...", # "about" from example, expanded
                "work_experience": [
                    {
                        "title": "Library Media Specialist",
                        "company": "Greeneville City Schools, Greeneville High School",
                        "dates": "Aug 2020 - Present (Simulated)"
                    },
                    {
                        "title": "Teacher",
                        "company": "Some Other School (Simulated)",
                        "dates": "Jan 2018 - Jul 2020 (Simulated)"
                    }
                ],
                "education": [
                    {
                        "institution": "University of Education (Simulated)",
                        "degree": "M.Ed. Library Science (Simulated)",
                        "field_of_study": "Library Science (Simulated)",
                        "dates": "2016 - 2018 (Simulated)"
                    }
                ],
                "skills": ["Media Management (Simulated)", "Curriculum Development (Simulated)", "Information Literacy (Simulated)"],
                "profile_url": url,
                "raw_brightdata_response_simulation_note": "This is a simulated structure. Actual BrightData API is async."
            }
            
            # In a real implementation with an async API, you would likely store the job_id
            # and have another mechanism to retrieve results.
            # For this subtask, returning the simulated structure after a successful trigger.
            
            return simulated_profile_data

        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to trigger LinkedIn profile scrape via BrightData: {str(e)}"}
        except Exception as e:
            # Catch any other unexpected errors
            return {"error": f"An unexpected error occurred: {str(e)}"}

    async def _fetch_hunter_company_data(self, domain: str) -> Optional[Dict]:
        """Helper function to fetch company data from Hunter.io"""
        if not self.hunter_api_key:
            # This case should ideally be caught before calling, but as a safeguard:
            return None 
        
        api_url = f"https://api.hunter.io/v2/companies/find?domain={domain}&api_key={self.hunter_api_key}"
        try:
            response = requests.get(api_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json().get("data")
        except requests.exceptions.RequestException as e:
            print(f"Hunter API request failed for {domain}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON from Hunter API for {domain}: {e}")
            return None

    async def _get_company_basic_info(self, domain: str, hunter_data: Optional[Dict] = None) -> Dict:
        """Get basic info for company using Hunter.io data."""
        if not hunter_data: # Fallback if not pre-fetched
            if not self.hunter_api_key:
                return {"company_name": "N/A", "description": "N/A", "location": "N/A", "website": domain}
            hunter_data = await self._fetch_hunter_company_data(domain)

        if not hunter_data:
            return {"company_name": "N/A", "description": "N/A", "location": "N/A", "website": domain}

        return {
            "company_name": hunter_data.get("name", "N/A"),
            "description": hunter_data.get("description", "N/A"),
            "location": hunter_data.get("location", "N/A"), # Example: "Wilmington, Delaware, United States"
            "website": hunter_data.get("domain", domain) # Hunter provides domain, ensure it matches input
        }

    async def _estimate_company_size(self, domain: str, hunter_data: Optional[Dict] = None) -> Optional[int]:
        """Estimate company size using Hunter.io data."""
        if not hunter_data: # Fallback if not pre-fetched
            if not self.hunter_api_key:
                return None
            hunter_data = await self._fetch_hunter_company_data(domain)
            
        if not hunter_data:
            return None

        size_str = hunter_data.get("metrics", {}).get("employees") # Example: "11-50", "501-1000", "10000+"
        if not size_str:
            return None

        try:
            if "-" in size_str:
                low, high = map(int, size_str.split('-'))
                return (low + high) // 2
            elif "+" in size_str:
                return int(size_str.replace("+", ""))
            else:
                return int(size_str)
        except ValueError:
            return None


    async def _get_industry_classification(self, domain: str, hunter_data: Optional[Dict] = None) -> Optional[str]:
        """Get industry classification using Hunter.io data."""
        if not hunter_data: # Fallback if not pre-fetched
            if not self.hunter_api_key:
                return None
            hunter_data = await self._fetch_hunter_company_data(domain)

        if not hunter_data:
            return None
            
        return hunter_data.get("category", {}).get("industry") # Example: "Internet Software & Services"


    async def company_research(self, domain: str) -> Dict:
        """Research company information using Hunter.io API."""
        if not self.hunter_api_key:
            return {"error": "HUNTER_API_KEY not found in environment variables."}

        # Fetch data once and pass to helpers
        hunter_data = await self._fetch_hunter_company_data(domain)

        if hunter_data is None:
            # This means the API call failed (network error, auth error, or domain not found by Hunter)
            # Return basic structure with N/A and the domain, plus an error message.
            return {
                "domain": domain,
                "company_name": "N/A",
                "description": "N/A",
                "location": "N/A",
                "employee_count": None,
                "industry": "N/A",
                "error": f"Failed to fetch data from Hunter.io for domain: {domain}. API key might be invalid or domain not found."
            }
            
        company_basic_info = await self._get_company_basic_info(domain, hunter_data)
        employee_count = await self._estimate_company_size(domain, hunter_data)
        industry_info = await self._get_industry_classification(domain, hunter_data)

        return {
            "domain": domain,
            **company_basic_info, # company_name, description, location, website
            "employee_count": employee_count,
            "industry": industry_info if industry_info else "N/A", # Ensure "N/A" if None
        }

    def _extract_name(self, soup) -> str:
        """Extract name from LinkedIn profile soup"""
        name_tag = soup.find('h1')
        return name_tag.get_text(strip=True) if name_tag else "N/A"

    def _extract_title(self, soup) -> str:
        """Extract title from LinkedIn profile soup"""
        title_tag = soup.find('div', class_=re.compile('top-card-layout__entity-info-container'))
        if title_tag:
            title_element = title_tag.find('div', class_=re.compile('top-card-layout__entity-info-container'))
            if title_element:
                 # This is a common pattern, but LinkedIn's class names are dynamic.
                 # A more robust solution would involve inspecting the HTML structure.
                 # For now, a simplified approach.
                 # Attempt to find a common title pattern
                 title_match = re.search(r'title:\s*"([^"]+)"', str(soup))
                 if title_match:
                     return title_match.group(1)
        return "N/A"

    def _extract_company(self, soup) -> str:
        """Extract company from LinkedIn profile soup"""
        company_tag = soup.find('a', class_=re.compile('top-card-link'))
        if company_tag:
             # Similar to title, class names are dynamic.
             # Look for common patterns or data attributes.
             company_match = re.search(r'company:\s*"([^"]+)"', str(soup))
             if company_match:
                 return company_match.group(1)
        return "N/A"

    def _extract_location(self, soup) -> str:
        """Extract location from LinkedIn profile soup"""
        location_tag = soup.find('span', class_=re.compile('top-card-layout__entity-info-container'))
        if location_tag:
             # Look for common patterns or data attributes.
             location_match = re.search(r'location:\s*"([^"]+)"', str(soup))
             if location_match:
                 return location_match.group(1)
        return "N/A"

    # Note: The original simulated helper methods _get_company_basic_info, 
    # _estimate_company_size, and _get_industry_classification that were here
    # have been replaced by Hunter.io API integrated versions above.
    # The old `_extract_` methods for LinkedIn are still present as they might be used elsewhere or by other tools.

    async def crm_update(self, lead_data: dict) -> Dict:
        """
        Sends lead data to a CRM webhook.
        The method expects CRM_WEBHOOK_URL to be set in environment variables.
        The receiving webhook is responsible for mapping fields from lead_data to the CRM.
        Note: This method uses the synchronous `requests` library within an async function
        for consistency with other tools in this file. For true non-blocking async behavior,
        an async HTTP client like httpx or aiohttp would be preferred.
        """
        if not self.crm_webhook_url:
            return {"status": "error", "message": "CRM_WEBHOOK_URL is not set. Cannot send data to CRM."}

        try:
            # Sending lead_data as JSON payload
            # The `requests` library will block here until the request completes.
            response = requests.post(
                self.crm_webhook_url, 
                json=lead_data, 
                headers=self.headers, # self.headers now includes 'Content-Type': 'application/json'
                timeout=15 # Adding a timeout
            )
            
            # Check if the request was successful (2xx status code)
            if response.status_code >= 200 and response.status_code < 300:
                return {
                    "status": "success", 
                    "message": f"Lead data successfully sent to CRM webhook. Status code: {response.status_code}"
                }
            else:
                return {
                    "status": "error", 
                    "message": f"CRM webhook returned an error. Status code: {response.status_code}. Response: {response.text}"
                }
        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Request to CRM webhook timed out."}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": f"Failed to send data to CRM webhook: {str(e)}"}
        except Exception as e:
            # Catch any other unexpected errors
            return {"status": "error", "message": f"An unexpected error occurred during CRM update: {str(e)}"}

    async def qualification_score(self, profile: dict, icp_config: dict) -> Dict:
        """
        Calculates a qualification score based on profile data and a structured Ideal Customer Profile (ICP) configuration.
        """
        score = 0
        reasoning_list = []

        # 1. Company Size
        employee_count = profile.get("employee_count")
        size_range = icp_config.get("company_size_range", [0, 0])
        size_weight = icp_config.get("company_size_weight", 0)
        if employee_count is not None:
            if size_range[0] <= employee_count <= size_range[1]:
                score += int(100 * size_weight)
                reasoning_list.append(f"Company size ({employee_count} employees) is within the ideal range ({size_range[0]}-{size_range[1]}). (+{int(100*size_weight)} pts)")
            else:
                reasoning_list.append(f"Company size ({employee_count} employees) is outside the ideal range ({size_range[0]}-{size_range[1]}). (0 pts)")
        else:
            reasoning_list.append("Company size information is unavailable. (0 pts)")

        # 2. Budget Authority
        title = profile.get("current_title", "").lower()
        budget_keywords = icp_config.get("budget_authority_keywords", [])
        budget_weight = icp_config.get("budget_authority_weight", 0)
        if any(keyword.lower() in title for keyword in budget_keywords):
            score += int(100 * budget_weight)
            reasoning_list.append(f"Title ('{profile.get('current_title', '')}') suggests budget authority. (+{int(100*budget_weight)} pts)")
        else:
            reasoning_list.append(f"Title ('{profile.get('current_title', '')}') does not clearly suggest budget authority. (0 pts)")

        # 3. Pain Points
        pain_keywords = icp_config.get("pain_point_keywords", [])
        pain_weight = icp_config.get("pain_point_weight", 0)
        text_to_search = []
        linkedin_summary = profile.get("summary_about_section", "")
        company_description = profile.get("description", "") 
        
        if linkedin_summary:
            text_to_search.append(linkedin_summary.lower())
        if company_description:
            text_to_search.append(company_description.lower())
        
        found_pain_points = False
        if text_to_search and pain_keywords:
            combined_text = " ".join(text_to_search)
            if any(keyword.lower() in combined_text for keyword in pain_keywords):
                score += int(100 * pain_weight)
                found_pain_points = True
                reasoning_list.append(f"Keywords related to pain points found in profile/company description. (+{int(100*pain_weight)} pts)")
        
        if not found_pain_points:
            reasoning_list.append("No clear keywords related to pain points found. (0 pts)")

        # 4. Engagement Level
        engagement_min_summary_length = icp_config.get("engagement_min_summary_length", 0)
        engagement_weight = icp_config.get("engagement_weight", 0)
        engagement_partial_summary_length = engagement_min_summary_length // 2 # Example for partial score

        if linkedin_summary and len(linkedin_summary) >= engagement_min_summary_length:
            score += int(100 * engagement_weight)
            reasoning_list.append(f"LinkedIn profile summary is present and detailed (length >= {engagement_min_summary_length}). (+{int(100*engagement_weight)} pts)")
        elif linkedin_summary and len(linkedin_summary) >= engagement_partial_summary_length : # Summary exists but is shorter than min_length but longer than partial
            score += int(100 * engagement_weight * 0.5) # Partial score
            reasoning_list.append(f"LinkedIn profile summary is present but brief (length < {engagement_min_summary_length}, but >= {engagement_partial_summary_length}). (+{int(100*engagement_weight*0.5)} pts)")
        else:
            reasoning_list.append(f"LinkedIn profile summary is missing or very short (length < {engagement_partial_summary_length}). (0 pts)")
        
        # Ensure score is within a reasonable range (0-100)
        score = max(0, min(100, score))

        # Determine recommendation based on score (thresholds from ICP or default)
        # For now, using the same thresholds as before, but could be part of icp_config
        pursue_threshold = icp_config.get("pursue_threshold", 70)
        nurture_threshold = icp_config.get("nurture_threshold", 50)

        if score >= pursue_threshold:
            recommendation = "pursue"
        elif score >= nurture_threshold:
            recommendation = "nurture"
        else:
            recommendation = "disqualify"

        final_reasoning = ". ".join(reasoning_list)
        if not final_reasoning:
            final_reasoning = "No specific scoring criteria met or data unavailable."
            
        return {"score": score, "recommendation": recommendation, "reasoning": final_reasoning}
