# setup.py - Script de inicialización
import asyncio
import os
from dotenv import load_dotenv
from backend.database.supabase_client import SupabaseClient
from backend.providers.multi_provider import MultiProvider

async def setup_database():
    """Setup database tables and initial data"""
    print("📊 Setting up database...")
    
    db = SupabaseClient()
    
    # Test connection
    try:
        await db.test_connection()
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Create initial data if needed
    print("✅ Database setup completed")
    return True

async def test_providers():
    """Test all LLM providers"""
    print("🤖 Testing LLM providers...")
    
    provider = MultiProvider()
    
    test_prompt = "Hello, this is a test. Please respond with 'Test successful'."
    
    # Test each provider
    for provider_name in ["openai", "claude", "gemini"]:
        try:
            result = await provider.complete(
                prompt=test_prompt,
                provider=provider_name,
                max_tokens=10
            )
            print(f"✅ {provider_name.upper()} provider working")
        except Exception as e:
            print(f"❌ {provider_name.upper()} provider failed: {e}")
    
    print("✅ Provider testing completed")

async def main():
    """Main setup function"""
    print("🚀 Starting AI Agents Suite Setup...")
    
    # Check environment variables
    required_vars = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", 
        "GOOGLE_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Missing environment variables: {missing_vars}")
        return
    
    # Setup database
    db_success = await setup_database()
    if not db_success:
        return
    
    # Test providers
    await test_providers()
    
    print("🎉 Setup completed successfully!")
    print("🚀 You can now start the API server with: python main.py")

if __name__ == "__main__":
    asyncio.run(main())
