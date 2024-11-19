import streamlit as st
from dataclasses import dataclass
from typing import List, Optional, Iterator
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS
from langchain_core.runnables import RunnablePassthrough
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from multi_doc_loader import MultiFileLoader
from reset_docs import DirectoryManager
import os


@dataclass
class ChatbotConfig:
    """Configurações do chatbot."""
    base_model: str
    temperature: float
    embedding_model: str
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    documents: Optional[List] = None
    processed_docs: Optional[List] = None

class ChatbotUI:
    """Gerencia a interface do usuário do chatbot."""
    
    def __init__(self):
        self._initialize_session_state()
        self._setup_page_config()
        
    def _initialize_session_state(self):
        """Inicializa o estado da sessão."""
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                AIMessage(content="Olá! 😊 Eu sou a Ada, sua assistente dedicada e pronta para ajudar. O que posso fazer por você hoje? 💡")
            ]
        if "processed_documents" not in st.session_state:
            st.session_state.processed_documents = False
        if "rag_documents" not in st.session_state:
            st.session_state.rag_documents = None
        if "temp_dir" not in st.session_state:
            st.session_state.temp_dir = None
    
    def _setup_page_config(self):
        """Configura a página do Streamlit."""
        st.set_page_config(page_title="Mesafold Application", page_icon="💬")
        st.title("Mesafold")
        st.info("Esta aplicação de IA pode cometer erros, devido ao uso de modelos de terceiros. Considere verificar informações importantes.", icon="ℹ️")
        
        
    def reset_chat(self):
        """Limpa o histórico do chat."""
        st.session_state.chat_history = []
        
    def process_documents(self, files, openai_api_key):
        """Processa os documentos enviados."""
        if files and openai_api_key:
            try:
                local_dir = "documentos"
                os.makedirs(local_dir, exist_ok=True) 

                for uploaded_file in files:
                    with open(os.path.join(local_dir, uploaded_file.name), 'wb') as f:
                        f.write(uploaded_file.getbuffer())

                loader = MultiFileLoader(
                    directory_path=local_dir,
                    glob_pattern="**/*.*",
                    api_key=openai_api_key,
                    faiss_index_path=os.path.join(local_dir, "faiss_index_chatbot")
                )                
                documents = loader.load()
                
                st.session_state.rag_documents = documents
                st.session_state.processed_documents = True

                st.success(f"Documentos processados com sucesso! Total de documentos: {len(documents)}")
                
                return documents

            except Exception as e:
                st.error(f"Erro ao processar documentos: {str(e)}")
                st.session_state.processed_documents = False
                return None
                
        else:
            if not files:
                st.warning("Por favor, selecione algum documento para processar.")
            if not openai_api_key:
                st.warning("Por favor, insira a chave da API OpenAI para processar os documentos.")
            return None

    def render_sidebar(self) -> ChatbotConfig:
        """Renderiza a barra lateral e retorna as configurações."""
        with st.sidebar:
            st.title("Configurações do chatbot")

            st.subheader("Configuração das APIs")
            # Config da API Groq
            groq_api_key = st.text_input(
                "Groq API Key",
                type='password',
                key='groq_api_key',
                label_visibility="visible",
                placeholder='Insira sua chave da Groq'
            )

            # Config da API OpenAI
            openai_api_key = st.text_input(
                "OpenAI API Key",
                type='password',
                key='openai_api_key',
                label_visibility="visible",
                placeholder='Insira sua chave da OpenAI'
            )
            
            st.divider()
            
            # file uploader
            st.subheader("Configuração do RAG")
            uploaded_files = st.file_uploader(
                "Selecione seus documentos para realizar o RAG",
                accept_multiple_files=True,
                type=['pdf', 'txt', 'csv', 'doc', 'docx', 'xlsx'],
                help="Arraste e solte os documentos para RAG"
            )


            # botão para processar os documentos do file uploader
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button('Processar Documentos'):
                    processed_docs = self.process_documents(uploaded_files, openai_api_key)
            with col2:
                if st.session_state.processed_documents:
                    st.success("✓ Processado")
                else:
                    st.info("Aguardando...")

            with st.expander("Banco de dados de conhecimento"):
                st.write("Todos os dados e documentos inseridos ao aplicativo estão contidos no **banco de dados de conhecimento**.")
                st.write("Para reiniciar o conhecimento da Ada, apague os dados.")
                if st.button("Apagar dados", type="primary"):
                    manager_dir = DirectoryManager("documentos")
                    manager_dir.dir_erase()
                    st.success("Banco de dados de conhencimento foi reiniciado.")
            
            st.divider()            
            
            # seleção dos modelos e configurações
            st.subheader("Modelo base")
            base_model = st.selectbox(
                "Selecione o modelo base do chatbot",
                ("llama-3.1-70b-versatile", "llama-3.1-8b-instant", "gpt-4o", "gpt-4o-mini")
            )
            
            st.subheader("Temperatura")
            temperature = st.slider(
                "Selecione a temperatura do modelo",
                value=0.6,
                min_value=0.0,
                max_value=1.0,
                step=0.1
            )
            
            st.subheader("Modelo de embeddings")
            embedding_model = st.selectbox(
                "Selecione o modelo de embeddings",
                ("text-embedding-3-small",)
            )
            
            return ChatbotConfig(
                base_model=base_model,
                temperature=temperature,
                embedding_model=embedding_model,
                groq_api_key=groq_api_key,
                openai_api_key=openai_api_key,
                documents=uploaded_files,
                processed_docs=st.session_state.get('rag_documents', None)
            )
    
    def render_chat_history(self):
        """Renderiza o histórico do chat."""
        for message in st.session_state.chat_history:
            with st.chat_message("AI" if isinstance(message, AIMessage) else "Human"):
                st.write(message.content)


class ChatbotBackend:
    """Gerencia a lógica do chatbot."""
    
    CHAT_TEMPLATE = """
    # AVATAR
    Você é uma assistente prestativa, carismática e atenciosa chamada ‘Ada’. 
    Sua função é atender seus usuários com dúvidas referentes aos documentos ingeridos pelo sistema RAG da plataforma ‘Mesafold’.

    # ROTEIRO
    Ajude seus usuários em suas tomadas de decisão baseadas em fatos, documentos e outros dados, resolvendo dúvidas e questões sobre documentos e outros tópicos, caso o usuário sinta vontade.

    # OBJETIVO
    Seu objetivo é resolver dúvidas e outros problemas referentes aos documentos que são ingeridos dentro da plataforma ‘Mesafold’ por meio do RAG. 
    Auxilie seus usuários em suas tomadas de decisão e seja atenciosa aos detalhes.

    # MODELO
    Exiba o resultado das respostas ao usuário em partes, com um resumo claro, objetivo e eficiente (apenas quando o usuário possuir ou fornecer os dados e documentos). Caso contrário, seja simples, clara e objetiva com as perguntas e respostas. 
    Caso a resposta seja grande, divida-a em tópicos e, por fim, acrescente sugestões, podendo ser baseadas na resolução de problemas ou conselhos eficientes de como resolver um problema — sempre com base em fatos, documentos ou dados disponíveis ao seu alcance que possam ajudar o usuário.

    # PANORAMA
    Seu usuário é uma pessoa especialista do meio corporativo que deseja usar documentos, fatos ou outros dados para auxiliar na tomada de decisões no negócio. 
    Aqui estão alguns exemplos de usuários que você deverá atender: advogados, médicos, engenheiros, empreendedores, vendedores, analistas, etc.

    # TRANSFORMAR
    Feito isso, agora você possui a liberdade para revisar sua resposta e analisar possíveis mudanças ou aprimorações nas respostas. 
    Sempre que necessário, use os fatos, documentos e outros dados para auxiliar no aprimoramento das informações.

    Contexto do documento: {context}
    Responda às perguntas a seguir considerando o histórico da conversa e o conteúdo do prompt:
    Histórico de bate-papo: {chat_history}
    Pergunta do usuário: {user_question}
    """
    
    def __init__(self, config: ChatbotConfig):
        self.config = config
        self.prompt = ChatPromptTemplate.from_template(self.CHAT_TEMPLATE)
        
    def _get_llm(self):
        """Retorna o modelo de linguagem apropriado."""
        if self.config.base_model.startswith("llama"):
            if not self.config.groq_api_key:
                raise ValueError("API key da Groq é necessária para modelos Llama")
            return ChatGroq(
                model=self.config.base_model,
                temperature=self.config.temperature,
                api_key=self.config.groq_api_key
            )
        elif self.config.base_model.startswith("gpt"):
            if not self.config.openai_api_key:
                raise ValueError("API key da OpenAI é necessária para modelos GPT")
            return ChatOpenAI(
                model=self.config.base_model,
                temperature=self.config.temperature,
                api_key=self.config.openai_api_key
            )
        else:
            raise ValueError(f"Modelo não suportado: {self.config.base_model}")
    
    def format_docs(self, docs):
        return "\n\n".join(doc.page_content for doc in docs)
    
    def get_response(self, query: str, chat_history: List) -> Iterator[str]:
        """Gera uma resposta do chatbot."""
        embedding_fn = OpenAIEmbeddings(api_key=self.config.openai_api_key)
        
        if not os.path.exists("./documentos/faiss_index_chatbot"):
            # verifica se possui algum documento processado, se não, usa apenas a LLM
            chain = self.prompt | self._get_llm() | StrOutputParser()
            return chain.stream({
                "context": "",
                "chat_history": chat_history,
                "user_question": query,
            })
        
        # se possuir os documentos, realiza o RAG
        vectorstore = FAISS.load_local(
            "./documentos/faiss_index_chatbot", 
            embeddings=embedding_fn,
            allow_dangerous_deserialization=True
        )
        
        chain = (
            RunnablePassthrough.assign(
                context=lambda x: self.format_docs(
                    vectorstore.similarity_search(x["user_question"], k=3)
                )
            )
            | self.prompt
            | self._get_llm()
            | StrOutputParser()
        )
        
        return chain.stream({
            "chat_history": chat_history,
            "user_question": query,
        })

def main():
    """Função principal do aplicativo."""
    ui = ChatbotUI()
    config = ui.render_sidebar()
    
    # botão de reset
    st.button('Apagar conversa', on_click=ui.reset_chat)
    
    # renderizar histórico
    ui.render_chat_history()
    
    # input do usuário
    user_query = st.chat_input("Digite sua pergunta aqui")
    if user_query:
        st.session_state.chat_history.append(HumanMessage(content=user_query))
        with st.chat_message("Human"):
            st.markdown(user_query)
            
        try:
            # gerar e exibir resposta
            backend = ChatbotBackend(config)
            with st.chat_message("AI"):
                with st.spinner("Pensando..."):
                    response = st.write_stream(backend.get_response(user_query, st.session_state.chat_history))
                    
            st.session_state.chat_history.append(AIMessage(content=response))
            
        except ValueError as e:
            st.error(f"Erro: {str(e)}")
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado: {str(e)}")

if __name__ == "__main__":
    main()