import asyncio
from dotenv import load_dotenv
load_dotenv()


def main():
    from app.services.cache_service import cache_service

    user_id  = "test-user-001"
    question = "What is the refund policy?"
    answer   = "You can return products within 30 days. Contact support@example.com."

    print("--- Rate limit test ---")
    for i in range(1, 5):
        allowed, remaining = cache_service.check_rate_limit(user_id)
        print(f"  Request {i}: allowed={allowed}, remaining={remaining}")

    print("\n--- Cache test ---")
    # Should be None first time
    result = cache_service.get_cached_answer(user_id, question)
    print(f"  Before set: {result}")

    # Store it
    cache_service.set_cached_answer(user_id, question, answer)

    # Should return the answer now
    result = cache_service.get_cached_answer(user_id, question)
    print(f"  After set:  {result}")

    # Case variation should still hit cache
    result = cache_service.get_cached_answer(user_id, "WHAT IS THE REFUND POLICY?")
    print(f"  Uppercase:  {result}")

    print("\nAll cache tests passed.")


main()