from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
import os
import uuid
import qrcode
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# NOVO: Importações para SQLAlchemy
from flask_sqlalchemy import SQLAlchemy
# NOVO: Importação para variáveis de ambiente
from dotenv import load_dotenv

# NOVO: Carregar variáveis de ambiente do arquivo .env (útil para desenvolvimento local)
load_dotenv()

evento = Flask(__name__, template_folder='modelos', static_folder='estatico')

evento.secret_key = os.environ.get('SECRET_KEY', 'uma_chave_secreta_muito_segura')
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

# NOVO: Lógica de seleção do banco de dados
USE_DATABASE = os.environ.get('DATABASE_URL') is not None

if USE_DATABASE:
    evento.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    evento.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db = SQLAlchemy(evento)

    # NOVO: Modelos de dados para o banco
    class Inscricao(db.Model):
        id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        nome_completo = db.Column(db.String(100), nullable=False)
        nome_secundario = db.Column(db.String(100), nullable=True)
        telefone = db.Column(db.String(20), nullable=False)
        email = db.Column(db.String(100), nullable=False)
        tipo_ingresso = db.Column(db.String(20), nullable=False)
        comprovante_pix = db.Column(db.String(100), nullable=False)
        validado = db.Column(db.Boolean, default=False)

    class Admin(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(50), unique=True, nullable=False)
        password = db.Column(db.String(100), nullable=False)

    class EventoInfo(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        titulo = db.Column(db.String(255), nullable=False)
        subtitulo = db.Column(db.String(255), nullable=False)

    # NOVO: Função para inicializar o banco de dados
    def inicializar_banco():
        with evento.app_context():
            db.create_all()
            if not Admin.query.filter_by(username='Leandro').first():
                admin_user = Admin(username='Leandro', password='123456')
                db.session.add(admin_user)
            if not EventoInfo.query.first():
                evento_info = EventoInfo(titulo="Conferência de Discipulado", subtitulo="Discipulado e Legado - Formando a Próxima Geração")
                db.session.add(evento_info)
            db.session.commit()
else:
    # A lógica original do dicionário permanece
    ADMIN_CREDENTIALS = {
        'username': 'Leandro',
        'password': '123456'
    }
    inscritos = {}

# Dados do evento extraídos das imagens fornecidas
EVENT_LOCAL = "Real Classic Bahia - Hotel e Convenções\nOrla da Pituba - Rua Fernando Menezes de Góes, 165 - Salvador"
EVENT_DATE = "13 e 14 de Setembro"
EVENT_TIME = "Sábado: 18h / Domingo: 08h"

def get_event_title():
    if USE_DATABASE:
        info = EventoInfo.query.first()
        return info.titulo if info else "Conferência de Discipulado"
    else:
        if os.path.exists(evento.config['EVENT_TITLE_FILE']):
            with open(evento.config['EVENT_TITLE_FILE'], 'r', encoding='utf-8') as f:
                return f.read().strip()
        return "Conferência de Discipulado"

def get_event_subtitle():
    if USE_DATABASE:
        info = EventoInfo.query.first()
        return info.subtitulo if info else "Discipulado e Legado - Formando a Próxima Geração"
    else:
        if os.path.exists(evento.config['EVENT_SUBTITLE_FILE']):
            with open(evento.config['EVENT_SUBTITLE_FILE'], 'r', encoding='utf-8') as f:
                return f.read().strip()
        return "Discipulado e Legado - Formando a Próxima Geração"

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

    if USE_DATABASE:
        novo_inscrito = Inscricao(
            id=ingresso_id,
            nome_completo=nome_principal,
            nome_secundario=nome_secundario,
            telefone=telefone,
            email=email,
            tipo_ingresso=tipo_ingresso,
            comprovante_pix=comprovante_filename
        )
        db.session.add(novo_inscrito)
        db.session.commit()
    else:
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
        
        if USE_DATABASE:
            admin_user = Admin.query.filter_by(username=username, password=password).first()
            if admin_user:
                session['logged_in'] = True
                flash('Login realizado com sucesso!')
                return redirect(url_for('admin'))
            else:
                flash('Usuário ou senha inválidos.')
        else:
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

    if USE_DATABASE:
        inscritos_list = Inscricao.query.all()
        inscritos_dict = {i.id: i for i in inscritos_list}
        inscritos_count = len(inscritos_list)
    else:
        inscritos_dict = inscritos
        inscritos_count = len(inscritos)

    return render_template('admin.html', inscritos=inscritos_dict, event_title=event_title, event_subtitle=event_subtitle, inscritos_count=inscritos_count)


# --- Funções de Cabeçalho e Rodapé para o PDF ---
# (Essa parte permanece a mesma)

def header_and_footer_pdf(canvas_obj, doc):
    canvas_obj.saveState()

    logo_path = os.path.join(evento.static_folder, 'imagens', 'logo_casa_firme.png')
    
    if os.path.exists(logo_path):
        logo_pil_image = Image.open(logo_path)
        logo_width_in_points = logo_pil_image.width
        logo_height_in_points = logo_pil_image.height
        logo_img_reader = ImageReader(logo_pil_image)

        timbre_width = 1.5 * inch
        timbre_height = (timbre_width * logo_height_in_points) / logo_width_in_points
        canvas_obj.drawImage(logo_img_reader, 50, A4[1] - 70, width=timbre_width, height=timbre_height)

        watermark_width = 4 * inch
        watermark_height = (watermark_width * logo_height_in_points) / logo_width_in_points
        x_center = (A4[0] - watermark_width) / 2
        y_center = (A4[1] - watermark_height) / 2
        
        canvas_obj.setFillAlpha(0.15)
        canvas_obj.drawImage(logo_img_reader, x_center, y_center, width=watermark_width, height=watermark_height, mask='auto')
        canvas_obj.setFillAlpha(1.0)
    else:
        print(f"ATENÇÃO: A imagem da logo não foi encontrada em: {logo_path}")

    canvas_obj.setFont('Helvetica-Bold', 12)
    canvas_obj.setFillColorRGB(0, 0, 0)
    canvas_obj.drawCentredString(A4[0]/2, 30, "PAGO")

    canvas_obj.restoreState()


@evento.route('/validar_ingresso/<ingresso_id>')
def validar_ingresso(ingresso_id):
    if not is_authenticated():
        return redirect(url_for('login'))
    
    if USE_DATABASE:
        inscrito = Inscricao.query.get(ingresso_id)
        if inscrito and not inscrito.validado:
            inscrito.validado = True
            db.session.commit()
            
            qr_code_data = f"ingresso_id:{ingresso_id}"
            qr_code_img = qrcode.make(qr_code_data)
            qr_code_path_temp = os.path.join(evento.config['UPLOAD_FOLDER'], f"qr_{ingresso_id}.png")
            qr_code_img.save(qr_code_path_temp)

            pdf_path = os.path.join(evento.config['UPLOAD_FOLDER'], f"ingresso_{ingresso_id}.pdf")
            doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=36)
            story = []
            styles = getSampleStyleSheet()
            
            titulo_style = ParagraphStyle(name='Titulo', parent=styles['Normal'], fontSize=20, alignment=1, spaceAfter=12)
            subtitulo_style = ParagraphStyle(name='Subtitulo', parent=styles['Normal'], fontSize=12, alignment=1, spaceAfter=24)
            story.append(Paragraph(get_event_title(), titulo_style))
            story.append(Paragraph(get_event_subtitle(), subtitulo_style))
            
            inscrito_info = [
                ["Nome Completo:", inscrito.nome_completo],
                ["Telefone:", inscrito.telefone],
                ["Email:", inscrito.email],
                ["Tipo de Ingresso:", inscrito.tipo_ingresso],
                ["", ""]
            ]
            
            if inscrito.nome_secundario:
                inscrito_info.insert(1, ["Nome Secundário:", inscrito.nome_secundario])

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
            
            event_details = [
                ["Data:", EVENT_DATE],
                ["Horário:", EVENT_TIME],
                ["Local:", EVENT_LOCAL]
            ]
            
            details_table = Table(event_details, colWidths=[2.5*inch, 4*inch])
            details_table.setStyle(table_style)
            story.append(details_table)
            story.append(Spacer(1, 0.3*inch))
            
            qr_code_pdf_image = RLImage(qr_code_path_temp, width=2.5*inch, height=2.5*inch)
            story.append(qr_code_pdf_image)
            story.append(Paragraph("Apresente este QR Code na entrada do evento para validação.", styles['Italic']))

            doc.build(story, onFirstPage=header_and_footer_pdf, onLaterPages=header_and_footer_pdf)
            
            flash(f'Ingresso de {inscrito.nome_completo} validado com sucesso! O PDF foi gerado.')
            return redirect(url_for('admin'))
    else:
        if ingresso_id in inscritos and not inscritos[ingresso_id]['validado']:
            inscrito = inscritos[ingresso_id]
            inscrito['validado'] = True

            qr_code_data = f"ingresso_id:{ingresso_id}"
            qr_code_img = qrcode.make(qr_code_data)
            qr_code_path_temp = os.path.join(evento.config['UPLOAD_FOLDER'], f"qr_{ingresso_id}.png")
            qr_code_img.save(qr_code_path_temp)
            inscrito['qr_code_path'] = qr_code_path_temp

            pdf_filename = f"ingresso_{ingresso_id}.pdf"
            pdf_path = os.path.join(evento.config['UPLOAD_FOLDER'], pdf_filename)
            
            doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=36)
            story = []
            styles = getSampleStyleSheet()
            
            titulo_style = ParagraphStyle(name='Titulo', parent=styles['Normal'], fontSize=20, alignment=1, spaceAfter=12)
            subtitulo_style = ParagraphStyle(name='Subtitulo', parent=styles['Normal'], fontSize=12, alignment=1, spaceAfter=24)
            story.append(Paragraph(get_event_title(), titulo_style))
            story.append(Paragraph(get_event_subtitle(), subtitulo_style))
            
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
            
            event_details = [
                ["Data:", EVENT_DATE],
                ["Horário:", EVENT_TIME],
                ["Local:", EVENT_LOCAL]
            ]
            
            details_table = Table(event_details, colWidths=[2.5*inch, 4*inch])
            details_table.setStyle(table_style)
            story.append(details_table)
            story.append(Spacer(1, 0.3*inch))
            
            qr_code_pdf_image = RLImage(qr_code_path_temp, width=2.5*inch, height=2.5*inch)
            story.append(qr_code_pdf_image)
            story.append(Paragraph("Apresente este QR Code na entrada do evento para validação.", styles['Italic']))

            doc.build(story, onFirstPage=header_and_footer_pdf, onLaterPages=header_and_footer_pdf)

            flash(f'Ingresso de {inscrito["nome_completo"]} validado com sucesso! O PDF foi gerado.')
            return redirect(url_for('admin'))
    
    return "Ingresso não encontrado ou já validado.", 404

# --- Rotas de Admin (Continuação) ---

@evento.route('/admin/excluir_ingresso/<ingresso_id>', methods=['POST'])
def excluir_ingresso(ingresso_id):
    if not is_authenticated():
        flash("Você não tem permissão para realizar essa ação.")
        return redirect(url_for('login'))
    
    if USE_DATABASE:
        inscrito = Inscricao.query.get(ingresso_id)
        if inscrito:
            db.session.delete(inscrito)
            db.session.commit()
            flash("Inscrição excluída com sucesso.")
        else:
            flash("Erro: Inscrição não encontrada.")
    else:
        if ingresso_id in inscritos:
            del inscritos[ingresso_id]
            flash("Inscrição excluída com sucesso.")
        else:
            flash("Erro: Inscrição não encontrada.")
    
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
        
        if USE_DATABASE:
            admin_user = Admin.query.filter_by(username='Leandro').first()
            if admin_user and admin_user.password == old_password:
                admin_user.password = new_password
                db.session.commit()
                flash('Senha alterada com sucesso!')
            else:
                flash('Senha antiga incorreta.')
        else:
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

    if USE_DATABASE:
        evento_info = EventoInfo.query.first()
        if evento_info:
            evento_info.titulo = novo_titulo
            evento_info.subtitulo = novo_subtitulo
            db.session.commit()
            flash('Título e subtítulo do evento atualizados com sucesso!')
        else:
            flash('Erro: Informações do evento não encontradas no banco.', 'error')
    else:
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
    
    if USE_DATABASE:
        ingresso_data = Inscricao.query.get(ingresso_id)
        if not ingresso_data:
            flash("Inscrição não encontrada.")
            return redirect(url_for('admin'))
    else:
        if ingresso_id not in inscritos:
            flash("Inscrição não encontrada.")
            return redirect(url_for('admin'))
        ingresso_data = inscritos[ingresso_id]

    if request.method == 'POST':
        if USE_DATABASE:
            ingresso_data.nome_completo = request.form['nome_completo']
            ingresso_data.nome_secundario = request.form['nome_secundario']
            ingresso_data.telefone = request.form['telefone']
            ingresso_data.email = request.form['email']
            ingresso_data.tipo_ingresso = request.form['tipo_ingresso']
            db.session.commit()
        else:
            ingresso_data['nome_completo'] = request.form['nome_completo']
            ingresso_data['nome_secundario'] = request.form['nome_secundario']
            ingresso_data['telefone'] = request.form['telefone']
            ingresso_data['email'] = request.form['email']
            ingresso_data['tipo_ingresso'] = request.form['tipo_ingresso']
        flash("Inscrição atualizada com sucesso!")
        return redirect(url_for('admin'))

    return render_template('editar_ingresso.html', ingresso_id=ingresso_id, ingresso=ingresso_data)

@evento.route('/qr_code/<ingresso_id>')
def qr_code(ingresso_id):
    if USE_DATABASE:
        inscrito = Inscricao.query.get(ingresso_id)
        if inscrito and inscrito.validado:
            qr_code_path = os.path.join(evento.config['UPLOAD_FOLDER'], f"qr_{ingresso_id}.png")
            return send_from_directory(evento.config['UPLOAD_FOLDER'], os.path.basename(qr_code_path))
    else:
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
    # NOVO: Se o banco de dados for usado, inicialize-o
    if USE_DATABASE:
        inicializar_banco()
    evento.run(debug=True, host='0.0.0.0')