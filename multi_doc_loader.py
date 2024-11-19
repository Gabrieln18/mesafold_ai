from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import CSVLoader
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import UnstructuredWordDocumentLoader
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from typing_extensions import List, Optional
import glob

class MultiFileLoader:
    def __init__(
            self, directory_path: str, 
                 glob_pattern: str = "*.*", 
                 chunk_size: int = 1000, 
                 chunk_overlap: int = 200, 
                 separators: str = "\n", 
                 api_key: str = None, 
                 model_name: Optional[str] = "text-embedding-3-small", 
                 faiss_index_path: str = None
    ):
        self.directory_path = directory_path
        self.glob_pattern = glob_pattern
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators
        self.api_key = api_key
        self.model_name = model_name
        self.faiss_index_path = faiss_index_path

        self.embedding_model = OpenAIEmbeddings(api_key=self.api_key, model=self.model_name)

        self.faiss_db = self.__load_or_create_faiss_index()

    def __load_or_create_faiss_index(self) -> FAISS:
        try:
            return FAISS.load_local(self.faiss_index_path, embeddings=self.embedding_model, allow_dangerous_deserialization=True)
        except Exception as e:
            print(f"Erro ao carregar FAISS: {e}. Criando um novo índice.")
            documents = self.__load_new_database()
            self.__create_faiss_database(documents)
            self.__save_faiss_database()
            return self.faiss_db

    def __create_faiss_database(self, documents: List[str]):
        self.faiss_db = FAISS.from_documents(documents=documents, embedding=self.embedding_model)

    def __save_faiss_database(self):
        if not self.faiss_db:
            raise ValueError("O banco de dados FAISS não foi criado. Execute 'create_faiss_database' primeiro.")
        self.faiss_db.save_local(self.faiss_index_path)
        print(f"Banco de dados FAISS salvo no diretório '{self.faiss_index_path}'.")

    def __load_new_database(self):
        documents = []
        full_glob_pattern = f"{self.directory_path}/{self.glob_pattern}"
        file_paths = glob.glob(full_glob_pattern, recursive=True)

        for file_path in file_paths:
            try:
                documents.extend(self.__load_document(file_path))
            except ValueError as e:
                print(e)
            except Exception as e:
                print(f"Erro ao carregar {file_path}: {e}")

        chunked_documents = self.__chunk_split(documents)
        return chunked_documents

    def load(self) -> List[Document]:
        documents = []
        full_glob_pattern = f"{self.directory_path}/{self.glob_pattern}"
        file_paths = glob.glob(full_glob_pattern, recursive=True)

        for file_path in file_paths:
            try:
                documents.extend(self.__load_document(file_path))
            except ValueError as e:
                print(e)
            except Exception as e:
                print(f"Erro ao carregar {file_path}: {e}")

        chunked_documents = self.__chunk_split(documents)
        embeddings = self.embedding_model.embed_documents([doc.page_content for doc in chunked_documents])
        self.__insert_new_embeddings(chunked_documents, embeddings)
        return chunked_documents

    def __load_document(self, file_path: str) -> List[Document]:
        if file_path.endswith(".pdf"):
            return [PyPDFLoader(file_path).load()[0]]
        elif file_path.endswith(".csv"):
            return [CSVLoader(file_path).load()[0]]
        elif file_path.endswith(".txt"):
            return [TextLoader(file_path).load()[0]]
        elif file_path.endswith(".docx") or file_path.endswith(".doc"):
            return [UnstructuredWordDocumentLoader(file_path).load()[0]]
        elif file_path.endswith(".xlsx"):
            return [UnstructuredFileLoader(file_path).load()[0]]
        else:
            raise ValueError(f"Tipo de arquivo não suportado: {file_path}")

    def __chunk_split(self, documents: List[Document]) -> List[Document]:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators
        )
        return text_splitter.split_documents(documents)

    def __insert_new_embeddings(self, new_documents: List[Document], new_embeddings: List[List[float]]):
        text_embedding_pairs = list(zip([doc.page_content for doc in new_documents], new_embeddings))
        temp_store = FAISS.from_embeddings(text_embedding_pairs, self.embedding_model)

        start_id = len(self.faiss_db.docstore._dict)
        self.faiss_db.index.merge_from(temp_store.index)

        for i, text in enumerate(new_documents):
            str_id = str(start_id + i)
            self.faiss_db.docstore._dict[str_id] = text

            if isinstance(self.faiss_db.index_to_docstore_id, dict):
                self.faiss_db.index_to_docstore_id[start_id + i] = str_id
            else:
                self.faiss_db.index_to_docstore_id = {
                    j: self.faiss_db.index_to_docstore_id[j]
                    for j in range(len(self.faiss_db.index_to_docstore_id))
                }
                self.faiss_db.index_to_docstore_id[start_id + i] = str_id

        assert len(self.faiss_db.docstore._dict) == self.faiss_db.index.ntotal, (
            "Número de documentos não corresponde ao número de vetores"
        )

        self.faiss_db.save_local(self.faiss_index_path)
        print(f"Adicionados {len(new_documents)} novos documentos ao índice FAISS!")

    def search(self, query, k=5):
        query_embedding = self.embedding_model.embed_query(query)
        results = self.faiss_db.similarity_search_with_score_by_vector(query_embedding, k=k)
        return results

