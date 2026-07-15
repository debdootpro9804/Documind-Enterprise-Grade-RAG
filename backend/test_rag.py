import asyncio
from dotenv import load_dotenv
load_dotenv()


async def main():
    # First make sure we have something in Pinecone to query against.
    # Re-uses the test document from the ingestion test.
    from app.services.ingestion_service import ingestion_service
    from app.services.rag_service import rag_service

    test_user   = "test-user-001"
    test_doc_id = "test-doc-rag-001"

    sample_text = """
    The refund policy allows customers to return products within 30 days of purchase.
    Items must be in original condition with all packaging intact.
    Digital products are non-refundable once downloaded.
    To initiate a refund, contact support@example.com with your order number.
    Refunds are processed within 5-7 business days back to the original payment method.

    Our shipping policy covers standard and express options.
    Standard shipping takes 5-7 business days and costs 99 rupees.
    Express shipping takes 1-2 business days and costs 299 rupees.
    Free shipping is available on orders above 999 rupees.
    We currently ship to all major cities across India.
    """

    print("Step 1 — ingesting sample document into Pinecone...")
    await ingestion_service.ingest_document(
        file_bytes  = sample_text.encode("utf-8"),
        filename    = "company_policy.txt",
        user_id     = test_user,
        document_id = test_doc_id,
    )
    print("Ingestion done.\n")

    # Now test the RAG query
    questions = [
        "What is the refund policy?",
        "How long does standard shipping take?",
        "Can I get a refund on a digital product?",
    ]

    for question in questions:
        print(f"Question: {question}")
        print("Answer:   ", end="", flush=True)

        full_answer = []
        async for token in rag_service.query_stream(
            question = question,
            user_id  = test_user,
        ):
            print(token, end="", flush=True)
            full_answer.append(token)

        print("\n" + "-" * 60)


asyncio.run(main())