import os
import time
import psutil
from tqdm import tqdm

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.callbacks import get_openai_callback

from dotenv import load_dotenv
load_dotenv()

def print_ram():
    process = psutil.Process(os.getpid())
    ram_mb = process.memory_info().rss / 1024 / 1024
    print(f"[RAM] usage: {ram_mb:.2f} MB")

def print_time(operation_start_time: float):
    print(f"[TIME] elapsed: {time.time() - operation_start_time:.2f} sec")



curr_time = time.time()
print("Loading all PDF files from the resume dataset..")

# initialize PDF directory loader that recursively scans automatically loads into memory all PDF files found inside subdirectories
loader = PyPDFDirectoryLoader("data")

# load all PDFs as LangChain Document objects (1 Document = 1 page in a PDF); each Document contains:
# - page content (raw extracted text from the PDF)
# - metadata (file path, source file name, etc.)
docs = loader.load()

print(f"Loaded Document objects: {len(docs)}")
print_ram()
print_time(curr_time)


# -----
curr_time = time.time()
print("\nSplitting all Document objects into chunks..")

# initialize recursive character text splitter
# (this is required because long documents must be broken into manageable segments to improve embedding quality and retrieval precision in RAG systems)
# Chunk 1: [A --------- B]
# Chunk 2:       [B --------- C]
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000, # maximum number of characters per chunk
    chunk_overlap=200, # number of overlapping characters – overlap ensures that consecutive chunks share context to prevent information loss
)

# split each loaded Document object into multiple smaller chunks (also Document objects)
chunks = splitter.split_documents(docs)

print(f"Created chunks: {len(chunks)}")
print_ram()
print_time(curr_time)


# -----
curr_time = time.time()
print("\nGenerating embedding vectors for each chunk..")

# initialize embedding model – hosted service by OpenAI, accessed via OPENAI_API_KEY
embedding_model = OpenAIEmbeddings()

# convert each chunk (text) into an embedding vector using the provided model, and save the final vector database to disk; for each chunk: embedding vectors, Document object, metadata, index structure for fast similarity search

with get_openai_callback() as callback:

    vector_db = Chroma.from_documents(
        documents=tqdm(chunks, desc="Processed chunks"),
        embedding=embedding_model,
        persist_directory="./database"
    )

    vector_db.persist()

    print("\n[OPENAI INFO]")
    print(f"Token usage: {callback.total_tokens}")
    print(f"Estimated cost: ${callback.total_cost:.4f}")

print_ram()
print_time(curr_time)

print("\nDONE! Vector DB created successfully and saved to database/.")