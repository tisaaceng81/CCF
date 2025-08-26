from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
import os
import uuid
import qrcode
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

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

# Dados do evento extraídos das imagens fornecidas
EVENT_LOCAL = "Real Classic Bahia - Hotel e Convenções\nOrla da Pituba - Rua Fernando Menezes de Góes, 165 - Salvador"
EVENT_DATE = "13 e 14 de Setembro"
EVENT_TIME = "Sábado: 18h / Domingo: 08h"

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
    nome_principal = request.form['nome']
    nome_secundario = request.form.get('nome_secundario', '')
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
        'nome_completo': nome_principal,
        'nome_secundario': nome_secundario,
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
    inscritos_count = len(inscritos)
    return render_template('admin.html', inscritos=inscritos, event_title=event_title, event_subtitle=event_subtitle, inscritos_count=inscritos_count)

# --- Funções de Cabeçalho e Rodapé para o PDF ---

def header_and_watermark(canvas_obj, doc):
    canvas_obj.saveState()

    # Adicionar o logo 'Casa Firme' no canto superior esquerdo (timbre)
    try:
        logo_path = os.path.join(evento.static_folder, 'imagem', 'logo_casa_firme.jpg')
        logo_img = ImageReader(logo_path)
        canvas_obj.drawImage(logo_img, 50, A4[1] - 70, width=1.5 * inch, height=0.6 * inch)
    except Exception as e:
        print(f"Erro ao adicionar o logo no cabeçalho: {e}")

    # Adicionar a marca d'água 'Casa Firme' transparente no centro
    try:
        logo_path = os.path.join(evento.static_folder, 'imagem', 'logo_casa_firme.jpg')
        logo_img = ImageReader(logo_path)
        
        # Coordenadas e tamanho da marca d'água
        img_width = 3 * inch
        img_height = (img_width * logo_img.height) / logo_img.width
        x_center = (A4[0] - img_width) / 2
        y_center = (A4[1] - img_height) / 2
        
        canvas_obj.setFillAlpha(0.2)  # Define a transparência (20%)
        canvas_obj.drawImage(logo_img, x_center, y_center, width=img_width, height=img_height, mask='auto')
        canvas_obj.setFillAlpha(1.0)  # Volta a transparência para o padrão
        
    except Exception as e:
        print(f"Erro ao adicionar a marca d'água do logo: {e}")

    canvas_obj.restoreState()

def footer(canvas_obj, doc):
    canvas_obj.saveState()

    # Adicionar o timbre de 'CONFIRMAÇÃO DE PAGAMENTO' no rodapé
    canvas_obj.setFont('Helvetica-Bold', 12)
    canvas_obj.setFillColorRGB(0.5, 0.5, 0.5)
    canvas_obj.drawString(50, 30, "CONFIRMAÇÃO DE PAGAMENTO")
    
    canvas_obj.restoreState()


@evento.route('/validar_ingresso/<ingresso_id>')
def validar_ingresso(ingresso_id):
    if not is_authenticated():
        return redirect(url_for('login'))
    
    if ingresso_id in inscritos and not inscritos[ingresso_id]['validado']:
        inscrito = inscritos[ingresso_id]
        inscrito['validado'] = True

        # Geração do QR Code
        qr_code_data = f"ingresso_id:{ingresso_id}"
        qr_code_img = qrcode.make(qr_code_data)
        qr_code_filename = f"qr_{ingresso_id}.png"
        qr_code_path_temp = os.path.join(evento.config['UPLOAD_FOLDER'], qr_code_filename)
        qr_code_img.save(qr_code_path_temp)
        inscrito['qr_code_path'] = qr_code_path_temp

        # Geração do PDF do Ingresso
        pdf_filename = f"ingresso_{ingresso_id}.pdf"
        pdf_path = os.path.join(evento.config['UPLOAD_FOLDER'], pdf_filename)
        
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        story = []
        styles = getSampleStyleSheet()
        
        # Título e Subtítulo do Evento
        titulo_style = ParagraphStyle(name='Titulo', parent=styles['Normal'], fontSize=20, alignment=1, spaceAfter=12)
        subtitulo_style = ParagraphStyle(name='Subtitulo', parent=styles['Normal'], fontSize=12, alignment=1, spaceAfter=24)
        story.append(Paragraph(get_event_title(), titulo_style))
        story.append(Paragraph(get_event_subtitle(), subtitulo_style))
        
        # Informações do Ingresso
        inscrito_info = [
            ["Nome Completo:", inscrito['nome_completo']],
            ["Telefone:", inscrito['telefone']],
            ["Email:", inscrito['email']],
            ["Tipo de Ingresso:", inscrito['tipo_ingresso']],
            ["", ""]
        ]
        
        if inscrito['nome_secundario']:
            inscrito_info.insert(1, ["Nome Secundário:", inscrito['nome_secundario']])

        table_style = TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, 0), (-1, -1), 1, colors.black),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])

        t = Table(inscrito_info, colWidths=[2.5*inch, 4*inch])
        t.setStyle(table_style)
        story.append(t)
        story.append(Spacer(1, 0.3*inch))
        
        # Detalhes do Evento
        event_details = [
            ["Data:", EVENT_DATE],
            ["Horário:", EVENT_TIME],
            ["Local:", EVENT_LOCAL]
        ]
        
        details_table = Table(event_details, colWidths=[2.5*inch, 4*inch])
        details_table.setStyle(table_style)
        story.append(details_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Adicionar QR Code
        qr_code_pdf_image = Image(qr_code_path_temp, width=2.5*inch, height=2.5*inch)
        story.append(qr_code_pdf_image)
        story.append(Paragraph("Apresente este QR Code na entrada do evento para validação.", styles['Italic']))

        # Construir o documento aplicando as funções de cabeçalho e rodapé
        doc.build(story, onFirstPage=header_and_watermark, onLaterPages=footer)
        
        flash(f'Ingresso de {inscrito["nome_completo"]} validado com sucesso! O PDF foi gerado.')
        return redirect(url_for('admin'))
    
    return "Ingresso não encontrado ou já validado.", 404

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

@evento.route('/admin/editar_ingresso/<ingresso_id>', methods=['GET', 'POST'])
def editar_ingresso(ingresso_id):
    if not is_authenticated():
        return redirect(url_for('login'))

    if ingresso_id not in inscritos:
        flash("Inscrição não encontrada.")
        return redirect(url_for('admin'))

    ingresso_data = inscritos[ingresso_id]

    if request.method == 'POST':
        # Atualiza os dados
        ingresso_data['nome_completo'] = request.form['nome_completo']
        ingresso_data['nome_secundario'] = request.form['nome_secundario']
        ingresso_data['telefone'] = request.form['telefone']
        ingresso_data['email'] = request.form['email']
        ingresso_data['tipo_ingresso'] = request.form['tipo_ingresso']
        flash("Inscrição atualizada com sucesso!")
        return redirect(url_for('admin'))

    return render_template('editar_ingresso.html', ingresso_id=ingresso_id, ingresso=ingresso_data)

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

@evento.route('/ingresso/<filename>')
def ingresso_pdf(filename):
    return send_from_directory(evento.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    evento.run(debug=True, host='0.0.0.0')