from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
import os
import uuid
import qrcode
from PIL import Image

evento = Flask(__name__, template_folder='modelos', static_folder='estatico')

evento.secret_key = 'uma_chave_secreta_muito_segura' 
evento.config['UPLOAD_FOLDER'] = 'arquivos_enviados'
evento.config['GALLERY_FOLDER'] = 'estatico/galeria'
evento.config['BANNERS_FOLDER'] = 'estatico/banners'
evento.config['EVENT_TITLE_FILE'] = 'event_title.txt'
evento.config['EVENT_SUBTITLE_FILE'] = 'event_subtitle.txt'

if not os.path.exists(evento.config['UPLOAD_FOLDER']):
    os.makedirs(evento.config['UPLOAD_FOLDER'])
if not os.path.exists(evento.config['GALLERY_FOLDER']):
    os.makedirs(evento.config['GALLERY_FOLDER'])
if not os.path.exists(evento.config['BANNERS_FOLDER']):
    os.makedirs(evento.config['BANNERS_FOLDER'])

ADMIN_CREDENTIALS = {
    'username': 'Leandro',
    'password': '123456'
}

inscritos = {}

# Função para ler o título do evento
def get_event_title():
    if os.path.exists(evento.config['EVENT_TITLE_FILE']):
        with open(evento.config['EVENT_TITLE_FILE'], 'r', encoding='utf-8') as f:
            return f.read().strip()
    return "Conferência de Discipulado" # Título padrão

# Nova função para ler o subtítulo do evento
def get_event_subtitle():
    if os.path.exists(evento.config['EVENT_SUBTITLE_FILE']):
        with open(evento.config['EVENT_SUBTITLE_FILE'], 'r', encoding='utf-8') as f:
            return f.read().strip()
    return "Discipulado e Legado - Formando a Próxima Geração" # Subtítulo padrão

# --- Rotas do Site ---

@evento.route('/')
def pagina_inicial():
    gallery_photos = os.listdir(evento.config['GALLERY_FOLDER'])
    banners = os.listdir(evento.config['BANNERS_FOLDER'])
    banners.sort()
    latest_banner = banners[-1] if banners else None
    event_title = get_event_title()
    event_subtitle = get_event_subtitle()
    return render_template('pagina_inicial.html', gallery_photos=gallery_photos, latest_banner=latest_banner, event_title=event_title, event_subtitle=event_subtitle)

@evento.route('/registrar', methods=['POST'])
def registrar():
    nome = request.form['nome']
    telefone = request.form['telefone']
    email = request.form['email']
    tipo_ingresso = request.form['tipo_ingresso']
    comprovante = request.files['comprovante_pix']

    if not comprovante or not comprovante.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        flash('Documento inválido. Por favor, envie uma imagem como comprovante.')
        return redirect(url_for('pagina_inicial'))

    ingresso_id = str(uuid.uuid4())

    comprovante_filename = f"{ingresso_id}_{comprovante.filename}"
    comprovante_path = os.path.join(evento.config['UPLOAD_FOLDER'], comprovante_filename)
    comprovante.save(comprovante_path)

    inscritos[ingresso_id] = {
        'nome_completo': nome,
        'telefone': telefone,
        'email': email,
        'tipo_ingresso': tipo_ingresso,
        'comprovante_pix': comprovante_filename,
        'validado': False,
        'qr_code_path': None
    }
    
    flash('Seu registro foi enviado! Aguarde a validação do seu pagamento.')
    return redirect(url_for('pagina_inicial'))

# --- Rotas de Autenticação e Admin ---

@evento.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_CREDENTIALS['username'] and password == ADMIN_CREDENTIALS['password']:
            session['logged_in'] = True
            flash('Login realizado com sucesso!')
            return redirect(url_for('admin'))
        else:
            flash('Usuário ou senha inválidos.')
    return render_template('login.html')

@evento.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('pagina_inicial'))

def is_authenticated():
    return session.get('logged_in')

@evento.route('/admin')
def admin():
    if not is_authenticated():
        return redirect(url_for('login'))
    event_title = get_event_title()
    event_subtitle = get_event_subtitle()
    return render_template('admin.html', inscritos=inscritos, event_title=event_title, event_subtitle=event_subtitle)

@evento.route('/validar_ingresso/<ingresso_id>')
def validar_ingresso(ingresso_id):
    if not is_authenticated():
        return redirect(url_for('login'))
    
    if ingresso_id in inscritos:
        inscrito = inscritos[ingresso_id]
        inscrito['validado'] = True
        qr_code_data = f"ingresso_id:{ingresso_id}"
        qr_code_img = qrcode.make(qr_code_data)
        qr_code_filename = f"qr_{ingresso_id}.png"
        qr_code_path = os.path.join(evento.config['UPLOAD_FOLDER'], qr_code_filename)
        qr_code_img.save(qr_code_path)
        inscrito['qr_code_path'] = qr_code_path
        flash(f'Ingresso de {inscrito["nome_completo"]} validado com sucesso!')
    return redirect(url_for('admin'))

@evento.route('/admin/upload_fotos', methods=['GET', 'POST'])
def upload_fotos():
    if not is_authenticated():
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'fotos' in request.files:
            photos_to_upload = request.files.getlist('fotos')
            upload_type = request.form['upload_type']
            
            if upload_type == 'galeria':
                folder = evento.config['GALLERY_FOLDER']
                for photo in photos_to_upload:
                    if photo and photo.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        photo_filename = str(uuid.uuid4()) + os.path.splitext(photo.filename)[1]
                        photo_path = os.path.join(folder, photo_filename)
                        photo.save(photo_path)
                flash('Fotos da galeria enviadas com sucesso!')
            elif upload_type == 'banner':
                folder = evento.config['BANNERS_FOLDER']
                # Apaga o banner antigo antes de salvar o novo
                for filename in os.listdir(folder):
                    os.remove(os.path.join(folder, filename))
                
                for photo in photos_to_upload:
                    if photo and photo.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        photo_filename = str(uuid.uuid4()) + os.path.splitext(photo.filename)[1]
                        photo_path = os.path.join(folder, photo_filename)
                        photo.save(photo_path)
                flash('Novo banner enviado com sucesso!')
            
            return redirect(url_for('upload_fotos'))

    gallery_photos = os.listdir(evento.config['GALLERY_FOLDER'])
    banners = os.listdir(evento.config['BANNERS_FOLDER'])
    latest_banner = banners[-1] if banners else None
    return render_template('upload_fotos.html', gallery_photos=gallery_photos, latest_banner=latest_banner)

@evento.route('/admin/excluir_foto/<filename>', methods=['POST'])
def excluir_foto(filename):
    if not is_authenticated():
        return redirect(url_for('login'))
    
    file_path = os.path.join(evento.config['GALLERY_FOLDER'], filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f'A foto {filename} foi excluída com sucesso!')
    else:
        flash('Erro: O arquivo não foi encontrado.')
        
    return redirect(url_for('upload_fotos'))

@evento.route('/admin/excluir_banner', methods=['POST'])
def excluir_banner():
    if not is_authenticated():
        return redirect(url_for('login'))
    
    banner_folder = evento.config['BANNERS_FOLDER']
    banners = os.listdir(banner_folder)
    
    if banners:
        latest_banner = banners[-1]
        file_path = os.path.join(banner_folder, latest_banner)
        os.remove(file_path)
        flash('O banner foi excluído com sucesso!')
    else:
        flash('Não há nenhum banner para excluir.')
        
    return redirect(url_for('upload_fotos'))

@evento.route('/admin/alterar_senha', methods=['GET', 'POST'])
def alterar_senha():
    if not is_authenticated():
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        old_password = request.form['senha_antiga']
        new_password = request.form['nova_senha']
        if old_password == ADMIN_CREDENTIALS['password']:
            ADMIN_CREDENTIALS['password'] = new_password
            flash('Senha alterada com sucesso!')
        else:
            flash('Senha antiga incorreta.')
    return render_template('alterar_senha.html')

@evento.route('/admin/alterar_titulo_evento', methods=['POST'])
def alterar_titulo_evento():
    if not is_authenticated():
        return redirect(url_for('login'))
    
    novo_titulo = request.form['novo_titulo']
    novo_subtitulo = request.form['novo_subtitulo']
    
    if novo_titulo:
        with open(evento.config['EVENT_TITLE_FILE'], 'w', encoding='utf-8') as f:
            f.write(novo_titulo)
    else:
        flash('O título não pode estar vazio.', 'error')
    
    if novo_subtitulo:
        with open(evento.config['EVENT_SUBTITLE_FILE'], 'w', encoding='utf-8') as f:
            f.write(novo_subtitulo)
        flash('Título e subtítulo do evento atualizados com sucesso!')
    else:
        flash('O subtítulo não pode estar vazio.', 'error')
    
    return redirect(url_for('admin'))

# --- Rotas para servir arquivos ---

@evento.route('/qr_code/<ingresso_id>')
def qr_code(ingresso_id):
    if ingresso_id in inscritos and inscritos[ingresso_id]['validado']:
        qr_code_path = inscritos[ingresso_id]['qr_code_path']
        return send_from_directory(evento.config['UPLOAD_FOLDER'], os.path.basename(qr_code_path))
    return "Ingresso não validado ou não encontrado.", 404

@evento.route('/comprovante/<filename>')
def comprovante(filename):
    return send_from_directory(evento.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    evento.run(debug=True, host='0.0.0.0')