from flask import Flask, render_template, request, redirect, url_for, session
import os
import hashlib
import time
from werkzeug.utils import secure_filename
import shutil
from urllib.parse import unquote

UPLOAD_FOLDER = os.path.join('static', 'uploads')
EXCLUIDOS_FOLDER = os.path.join('static', 'excluidos')
app = Flask(__name__)
app.secret_key = 'seu_segredo_aqui'

# Definindo o caminho para a pasta Produtos
PRODUTOS_DIR = os.path.join(os.getcwd(), 'produtos')  # Caminho absoluto baseado no diretório atual

# Diretórios de usuários, produtos e excluídos
USERS_DIR = 'users'

if not os.path.exists(USERS_DIR):
    os.makedirs(USERS_DIR)
if not os.path.exists(PRODUTOS_DIR):
    os.makedirs(PRODUTOS_DIR)
if not os.path.exists(EXCLUIDOS_FOLDER):
    os.makedirs(EXCLUIDOS_FOLDER)

SESSION_TIMEOUT = 10 * 60  # 10 minutos em segundos

class Produto:
    def __init__(self, nome, preco, categoria, imagens, usuario):
        self.nome = nome
        self.preco = preco
        self.categoria = categoria
        self.imagens = imagens
        self.usuario = usuario

    def save(self):
        produto_id = f"{self.usuario}_{self.nome.replace(' ', '_').lower()}.txt"  # Convertendo para minúsculo e substituindo espaços por underlines
        with open(os.path.join(PRODUTOS_DIR, produto_id), 'w') as f:
            f.write(str(self.__dict__))

    @classmethod
    def load_all(cls):
        produtos = []
        for filename in os.listdir(PRODUTOS_DIR):
            with open(os.path.join(PRODUTOS_DIR, filename), 'r') as f:
                produto_data = eval(f.read())  # A forma de leitura do arquivo deve garantir que todos os dados sejam recuperados
                if 'usuario' not in produto_data:
                    continue  # Ignora produtos sem o campo 'usuario'
                produtos.append(cls(**produto_data))
        return produtos

    @classmethod
    def load_user_produtos(cls, usuario):
        produtos = []
        for filename in os.listdir(PRODUTOS_DIR):
            if filename.startswith(usuario):  # Filtra apenas os produtos do usuário
                with open(os.path.join(PRODUTOS_DIR, filename), 'r') as f:
                    produto_data = eval(f.read())  # Leitura do arquivo
                    produtos.append(cls(**produto_data))
        return produtos

    def move_to_exclusao(self):
        produto_id = f"{self.usuario}_{self.nome.replace(' ', '_').lower()}.txt"  # Convertendo para minúsculo e substituindo espaços por underlines
        produto_dir = os.path.join(PRODUTOS_DIR, produto_id)
        produto_backup_dir = os.path.join(EXCLUIDOS_FOLDER, produto_id)

        # Move o arquivo de produto
        if os.path.exists(produto_dir):
            print(f"Movendo arquivo de produto {produto_id} para {produto_backup_dir}")
            shutil.move(produto_dir, produto_backup_dir)
        
        # Move as imagens associadas ao produto
        for imagem in self.imagens:
            imagem_path = os.path.join(UPLOAD_FOLDER, imagem)
            if os.path.exists(imagem_path):
                imagem_backup_path = os.path.join(EXCLUIDOS_FOLDER, imagem)
                print(f"Movendo imagem {imagem} para {imagem_backup_path}")
                shutil.move(imagem_path, imagem_backup_path)

    @classmethod
    def remove(cls, produto_id):
        produto_id = produto_id.lower()  # Convertendo o ID para minúsculo para garantir correspondência
        produto_path = os.path.join(PRODUTOS_DIR, produto_id)
        try:
            if os.path.exists(produto_path):  # Verifica se o arquivo existe
                os.remove(produto_path)  # Remove o arquivo
                print(f"Produto {produto_id} removido com sucesso de {produto_path}.")
            else:
                print(f"Produto {produto_id} não encontrado no diretório {PRODUTOS_DIR}.")
        except Exception as e:
            print(f"Erro ao tentar remover o arquivo {produto_id}: {e}")


class Usuario:
    @staticmethod
    def save(email, password):
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        with open(os.path.join(USERS_DIR, email + '.txt'), 'w') as f:
            f.write(hashed_password)

    @staticmethod
    def user_exists(email):
        return os.path.exists(os.path.join(USERS_DIR, email + '.txt'))

    @staticmethod
    def check_password(email, password):
        try:
            with open(os.path.join(USERS_DIR, email + '.txt'), 'r') as f:
                stored_password = f.read()
            return stored_password == hashlib.sha256(password.encode()).hexdigest()
        except FileNotFoundError:
            return False

class Sessao:
    @staticmethod
    def is_session_active():
        last_activity = session.get('last_activity')
        if last_activity and (time.time() - last_activity > SESSION_TIMEOUT):
            return False
        session['last_activity'] = time.time()
        return True

    @staticmethod
    def check_session():
        if 'email' in session and not Sessao.is_session_active():
            session.clear()

# Função de salvar usuário
def save_user(email, password):
    Usuario.save(email, password)

# Função para verificar se o usuário existe
def user_exists(email):
    return Usuario.user_exists(email)

# Função para verificar a senha
def check_password(email, password):
    return Usuario.check_password(email, password)

# Função para verificar atividade da sessão
def is_session_active():
    return Sessao.is_session_active()

# Middleware para verificar sessão ativa
@app.before_request
def check_session():
    Sessao.check_session()

# Rota inicial
@app.route('/')
def index():
    if 'email' in session:
        produtos = Produto.load_all()
        return render_template('index.html', email=session['email'], produtos=produtos)
    return redirect(url_for('login'))

# Rota de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        if user_exists(email) and check_password(email, password):
            session['email'] = email
            session['last_activity'] = time.time()
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Email ou senha incorretos")
    return render_template('login.html')

# Rota para adicionar produtos
@app.route('/adicionar', methods=['GET', 'POST'])
def adicionar():
    categorias = ["Eletrônicos", "Roupas", "Alimentos", "Casa", "Esporte"]
    if request.method == 'POST':
        nome = request.form['nome']
        preco = request.form['preco']
        categoria = request.form['categoria']
        nova_categoria = request.form.get('nova_categoria')

        try:
            preco = float(preco)
        except ValueError:
            return "Erro: O preço deve ser um número válido.", 400

        if categoria == "nova" and nova_categoria:
            categoria = nova_categoria

        imagem = request.files['imagem']
        imagem_filename = secure_filename(imagem.filename)
        imagem_path = os.path.join(UPLOAD_FOLDER, imagem_filename)
        imagem.save(imagem_path)

        produto = Produto(
            nome=nome,
            preco=preco,
            categoria=categoria,
            imagens=[imagem_filename],
            usuario=session['email']
        )
        produto.save()
        return redirect(url_for('index'))
    return render_template('adicionar.html', categorias=categorias)

# Rota para exibir produtos do usuário
@app.route('/meus_produtos')
def meus_produtos():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    produtos = Produto.load_user_produtos(session['email'])
    return render_template('meus_produtos.html', produtos=produtos)

# Rota para cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if user_exists(email):
            return render_template('cadastro.html', error="Usuário já existe.")
        save_user(email, password)
        return redirect(url_for('login'))
    return render_template('cadastro.html')

# Rota para editar produto
@app.route('/editar/<produto_id>', methods=['GET', 'POST'])
def editar(produto_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    produto = None
    # Verifique se o produto existe e carregue-o
    for filename in os.listdir(PRODUTOS_DIR):
        if filename == produto_id.lower():  # Comparando o nome em minúsculo
            with open(os.path.join(PRODUTOS_DIR, filename), 'r') as f:
                produto_data = eval(f.read())  # Carrega os dados do produto
                produto = Produto(**produto_data)

    if produto is None or produto.usuario != session['email']:
        return redirect(url_for('index'))

    if request.method == 'POST':
        nome = request.form['nome']
        preco = request.form['preco']
        categoria = request.form['categoria']

        try:
            preco = float(preco)
        except ValueError:
            return "Erro: O preço deve ser um número válido.", 400

        imagem = request.files['imagem']
        imagem_filename = secure_filename(imagem.filename)
        imagem_path = os.path.join(UPLOAD_FOLDER, imagem_filename)
        imagem.save(imagem_path)

        produto.nome = nome
        produto.preco = preco
        produto.categoria = categoria
        produto.imagens = [imagem_filename]

        produto.save()  # Certifique-se de que esse método esteja funcionando
        return redirect(url_for('meus_produtos'))

    return render_template('editar.html', produto=produto)


@app.route('/excluir/<produto_id>', methods=['POST'])
def excluir(produto_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    produto_id = produto_id.lower()  # Convertendo o ID para minúsculo para garantir correspondência
    produto = None
    for filename in os.listdir(PRODUTOS_DIR):
        if filename == produto_id:
            with open(os.path.join(PRODUTOS_DIR, filename), 'r') as f:
                produto_data = eval(f.read())  # O que salva os dados do produto no arquivo
                produto = Produto(**produto_data)

    if produto is None or produto.usuario != session['email']:
        print(f"Produto não encontrado ou usuário não autorizado para excluir: {produto_id}")
        return redirect(url_for('meus_produtos'))  # Redireciona para a página de produtos do usuário

    produto.move_to_exclusao()
    produto.remove(produto_id)

    return redirect(url_for('meus_produtos'))


# Rota para logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
