from langchain.document_loaders import  PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain import PromptTemplate
import fitz
from typing import List
from rank_bm25 import BM25Okapi




def replace_t_with_space(list_of_documents):
    """
    Replaces all tab characters ('\t') with spaces in the page content of each document.

    Args:
        list_of_documents: A list of document objects, each with a 'page_content' attribute.

    Returns:
        The modified list of documents with tab characters replaced by spaces.
    """

    for doc in list_of_documents:
        doc.page_content = doc.page_content.replace('\t', ' ')  # Replace tabs with spaces
    return list_of_documents




def encode_pdf(path, chunk_size=1000, chunk_overlap=200):
    """
    Encodes a PDF book into a vector store using OpenAI embeddings.

    Args:
        path: The path to the PDF file.
        chunk_size: The desired size of each text chunk.
        chunk_overlap: The amount of overlap between consecutive chunks.

    Returns:
        A FAISS vector store containing the encoded book content.
    """

    # Load PDF documents
    loader = PyPDFLoader(path)
    documents = loader.load()

    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_function=len
    )
    texts = text_splitter.split_documents(documents)
    cleaned_texts = replace_t_with_space(texts)

    # Create embeddings and vector store
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(cleaned_texts, embeddings)

    return vectorstore


def retrieve_context_per_question(question, chunks_query_retriever):
    """
    Retrieves relevant context and unique URLs for a given question using the chunks query retriever.

    Args:
        question: The question for which to retrieve context and URLs.

    Returns:
        A tuple containing:
        - A string with the concatenated content of relevant documents.
        - A list of unique URLs from the metadata of the relevant documents.
    """

    # Retrieve relevant documents for the given question
    docs = chunks_query_retriever.get_relevant_documents(question)

    # Concatenate document content
    # context = " ".join(doc.page_content for doc in docs)
    context = [doc.page_content for doc in docs]

    
    return context

class QuestionAnswerFromContext(BaseModel):
    """
    Model to generate an answer to a query based on a given context.
    
    Attributes:
        answer_based_on_content (str): The generated answer based on the context.
    """
    answer_based_on_content: str = Field(description="Generates an answer to a query based on a given context.")

def create_question_answer_from_context_chain(llm):

    # Initialize the ChatOpenAI model with specific parameters
    question_answer_from_context_llm = llm

    # Define the prompt template for chain-of-thought reasoning
    question_answer_prompt_template = """ 
    For the question below, provide a concise but suffice answer based ONLY on the provided context:
    {context}
    Question
    {question}
    """

    # Create a PromptTemplate object with the specified template and input variables
    question_answer_from_context_prompt = PromptTemplate(
        template=question_answer_prompt_template,
        input_variables=["context", "question"],
    )

    # Create a chain by combining the prompt template and the language model
    question_answer_from_context_cot_chain = question_answer_from_context_prompt | question_answer_from_context_llm.with_structured_output(QuestionAnswerFromContext)
    return question_answer_from_context_cot_chain



def answer_question_from_context(question, context, question_answer_from_context_chain):
    """
    Answer a question using the given context by invoking a chain of reasoning.

    Args:
        question: The question to be answered.
        context: The context to be used for answering the question.

    Returns:
        A dictionary containing the answer, context, and question.
    """
    input_data = {
        "question": question,
        "context": context
    }
    print("Answering the question from the retrieved context...")

    output = question_answer_from_context_chain.invoke(input_data)
    answer = output.answer_based_on_content
    return {"answer": answer, "context": context, "question": question}


def show_context(context):
    """
    Display the contents of the provided context list.

    Args:
        context (list): A list of context items to be displayed.

    Prints each context item in the list with a heading indicating its position.
    """
    for i, c in enumerate(context):
        print(f"Context {i+1}:")
        print(c)
        print("\n")


def read_pdf_to_string(path):
    """
    Read a PDF document from the specified path and return its content as a string.

    Args:
        path (str): The file path to the PDF document.

    Returns:
        str: The concatenated text content of all pages in the PDF document.

    The function uses the 'fitz' library (PyMuPDF) to open the PDF document, iterate over each page,
    extract the text content from each page, and append it to a single string.
    """
    # Open the PDF document located at the specified path
    doc = fitz.open(path)
    content = ""
    # Iterate over each page in the document
    for page_num in range(len(doc)):
        # Get the current page
        page = doc[page_num]
        # Extract the text content from the current page and append it to the content string
        content += page.get_text()
    return content



def bm25_retrieval(bm25: BM25Okapi, cleaned_texts: List[str], query: str, k: int = 5) -> List[str]:
    """
    Perform BM25 retrieval and return the top k cleaned text chunks.

    Args:
    bm25 (BM25Okapi): Pre-computed BM25 index.
    cleaned_texts (List[str]): List of cleaned text chunks corresponding to the BM25 index.
    query (str): The query string.
    k (int): The number of text chunks to retrieve.

    Returns:
    List[str]: The top k cleaned text chunks based on BM25 scores.
    """
    # Tokenize the query
    query_tokens = query.split()

    # Get BM25 scores for the query
    bm25_scores = bm25.get_scores(query_tokens)

    # Get the indices of the top k scores
    top_k_indices = np.argsort(bm25_scores)[::-1][:k]

    # Retrieve the top k cleaned text chunks
    top_k_texts = [cleaned_texts[i] for i in top_k_indices]

    return top_k_texts
