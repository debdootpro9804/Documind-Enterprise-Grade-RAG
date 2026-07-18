import asyncio
from dotenv import load_dotenv
load_dotenv()

async def check_vision():
    from app.core.config import settings
    from openai import AsyncAzureOpenAI
    import base64
    import urllib.request

    client = AsyncAzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )
    from pathlib import Path
    image_path = Path("/Users/debdoot/Documents/Projects/documind/test_image/pothole.png")
    image_bytes = image_path.read_bytes()
    print(f"Image: {image_path.name}")
    print(f"Size:  {len(image_bytes):,} bytes ({len(image_bytes)/1024:.1f} KB)")

    # Create a tiny 1x1 red pixel PNG in pure Python — no download needed
    # This is a valid minimal PNG file hardcoded as bytes
    ext_to_mime = {
        ".jpg":  "jpeg",
        ".jpeg": "jpeg",
        ".png":  "png",
        ".webp": "webp",
        ".gif":  "gif",
    }
    ext  = image_path.suffix.lower()
    mime = ext_to_mime.get(ext, "jpeg")
    print(f"MIME:  image/{mime}\n")

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    print(f"Testing vision with image ({len(image_bytes)} bytes)...")
    print(f"Deployment: {settings.azure_openai_deployment_name}")
    print(f"API version: {settings.azure_openai_api_version}")

    try:
        response = await client.chat.completions.create(
                model=settings.azure_openai_deployment_name,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{mime};base64,{b64}",
                                "detail": "high",
                            },
                        },
                        {
                            "type": "text",
                            "text": "Describe this image in detail.",
                        },
                    ],
                }],
                max_tokens=200,
            )
        print(f"\nVision works! Response: {response.choices[0].message.content}")

    except Exception as e:
        print(f"\nVision failed: {e}")
        print("\nPossible causes:")
        print("  1. Your Azure API version doesn't support vision")
        print("     Try: AZURE_OPENAI_API_VERSION=2024-08-01-preview")
        print("  2. GPT-4o mini vision not enabled on your Azure deployment")
        print("  3. Your deployment is gpt-4o-mini but needs gpt-4o for vision")


asyncio.run(check_vision())