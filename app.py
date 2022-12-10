import os
import jinja2  
import psycopg2
import psycopg2.extras
from datetime import datetime
from flask import Flask, redirect, render_template, request, flash, send_from_directory
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'some random string'
app.config['UPLOAD_FOLDER'] = 'static/files'

def allowed_file(filename):
  return '.' in filename and \
    filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_currency(value):
  return 'R${:,.2f}'.format(value)
jinja2.filters.FILTERS['format_currency'] = format_currency   

   
def date_format(value):
  if isinstance(value, str):
    if value == '':
      return ''
    date_value = datetime.strptime(value, '%Y-%m-%d')
  else:
    date_value = value
  return date_value.strftime("%d/%m/%Y")
jinja2.filters.FILTERS['date_format'] = date_format 


def year_month_format(value):
  date_value = datetime.strptime(value, '%Y-%m')
  return date_value.strftime('%B %Y')
jinja2.filters.FILTERS['year_month_format'] = year_month_format


def word_list(value):
  if len(value) == 0:
    return ''
  result = value[0]
  for index, word in enumerate(value[1:]):
    if index < len(value) - 2:
      result += ','
    else:
      result += ' e'
    result += f' {word}'
  return result
jinja2.filters.FILTERS['word_list'] = word_list

@app.route('/', methods=['GET', 'POST'])
def index():

  connection = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  if request.method == 'POST':

    date = request.form['date']
    valor = request.form['valor']
    tags = request.form['tags']
    descricao = request.form['descricao']
    file = request.files['file']

    filename = secure_filename(file.filename)
    
    if date == '' or valor == '' or tags == '':
      return render_template('index.html', transacao={}, date=date, valor=valor, tags=tags)

    valor = float(valor)

    cursor.execute('''
      insert into transacoes (date, valor_em_cent, descricao, imgname)
      values (%s, %s, %s, %s)
      returning id;   
    ''', (date, valor*100, descricao, filename, ))      

    row = cursor.fetchone()
    id_transacao = row['id']

    if file and allowed_file(file.filename):
      file.save(os.path.join(app.config['UPLOAD_FOLDER'], str(id_transacao)))

    cursor.execute('''
      select id, nome
      from tags  
      where nome = (%s);
    ''', (tags, ))

    results = cursor.fetchall()

    if results == []: 

      cursor.execute('''
        insert into tags (nome)
        values (%s)
        returning id;   
      ''', (tags, ))

      tag_row = cursor.fetchone()
    else:
      tag_row = results[0]

    id_tag = tag_row['id']
    cursor.execute('''
      insert into transacao_tag (id_transacao, id_tag)
      values (%s, %s); 
    ''', (id_transacao, id_tag, ))       
      
    connection.commit()

    flash('Transaction created successfully!')
    return redirect('/')

  return render_template('index.html', transacao={})


@app.route('/consultar', methods=['GET'])
def consultar():

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  cur.execute('''
    select nome
    from tags;
  ''')

  results_tags = cur.fetchall()

  if request.method == 'GET':
    date = request.args.get('date', None)
    valor = request.args.get('valor', None)
    tags = request.args.getlist('tags', None)
    descricao = request.args.get('descricao', None)  

    insert_query = '''
      select tx.id, tx.date, tx.descricao, tx.valor_em_cent, tx.imgname, t.nome tag
      from transacoes tx
        inner join transacao_tag tg
          on tx.id = tg.id_transacao
        inner join tags t
          on t.id = tg.id_tag 
      where 1=1
    '''

    parametros = []

    if date:
      insert_query += '''
        and tx.date = %s
      '''
      parametros.append(date)

    if valor:
      insert_query += '''
        and tx.valor_em_cent = %s
      '''
      parametros.append(valor)

    if tags:
      insert_query += '''
        and nome in %s
      '''
      parametros.append(tuple(tags))

    if descricao:
      insert_query += '''
        and tx.descricao ilike %s
      '''
      parametros.append(f"%{descricao}%")

    cur.execute(insert_query, parametros)
    
    registros = cur.fetchall()
    transacoes = []

    for registro in registros:
      transacoes.append({
        'id': registro['id'],
        'date': registro['date'],
        'valor': registro['valor_em_cent']/100,
        'tags': registro['tag'],
        'descricao': registro['descricao'],
        'file': registro['imgname']
      })    

  return render_template('consultar.html', results_tags=results_tags, transacoes=transacoes, date=date, valor=valor, tags=tags, descricao=descricao)


@app.route('/uploads/<id_transacao>', methods=['GET'])
def download_file(id_transacao):

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cur = conn.cursor()

  cur.execute('''
    select imgname
    from transacoes
    where id = (%s);
  ''', (id_transacao, ))

  row = cur.fetchall()
  namefile = row[0]
  file_extension = ''.join(namefile)

  return send_from_directory(app.config['UPLOAD_FOLDER'], id_transacao, download_name=f'{id_transacao}{file_extension}', as_attachment=True)


@app.route('/transacoes/<int:id_transacao>/excluir', methods=['POST'])
def delete_transacoes(id_transacao):

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cur = conn.cursor()

  try:
    os.remove(f'static/files/{id_transacao}')
  except FileNotFoundError:
    pass

  delete_query = '''
    delete from transacao_tag where id_transacao = %s;
    delete from transacoes where id = %s;
  '''

  cur.execute(delete_query, (id_transacao, id_transacao, ))

  conn.commit()

  flash('Deleted successfully!')
  return redirect('/consultar', code = 303)


@app.route('/transacoes/edit/<int:id_transacao>', methods=['GET', 'POST'])
def edit_transacoes(id_transacao):

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  cur.execute('''
    select tx.id, tx.date, tx.descricao, tx.valor_em_cent, tx.imgname, t.nome "tag"
    from transacoes tx
      inner join transacao_tag tg
        on tx.id = tg.id_transacao
      inner join tags t
        on t.id = tg.id_tag
    where tx.id = %s;
  ''',(id_transacao, ))

  registros = cur.fetchall()

  for registro in registros:

    if registro['id'] == id_transacao:

      if request.method == 'POST':

        date = request.form['date']
        valor = float(request.form['valor'])
        tags = request.form['tags']
        descricao = request.form['descricao']
        file = request.files['file']

        filename = secure_filename(file.filename)

        if date == '' or valor == '' or tags == '':
          return render_template('index.html', transacao={}, date=date, valor=valor, tags=tags)

        if file and allowed_file(file.filename):

          try:
            os.remove(f'static/files/{id_transacao}')
          except FileNotFoundError:
            pass

          file.save(os.path.join(app.config['UPLOAD_FOLDER'], str(id_transacao)))                    

          edit_query = '''
            update transacoes 
            set 
              date = %s,
              valor_em_cent = %s,
              descricao = %s,
              imgname = %s 
            where id = %s;
            update tags t
            set
              nome = %s  
              where id in (
                select id_tag
                from transacao_tag
                where id_transacao = %s
              ); 
          '''

          cur.execute(edit_query, (date, valor*100, descricao, filename, id_transacao, tags, id_transacao, ))

        else:

          edit_query = '''
            update transacoes 
            set 
              date = %s,
              valor_em_cent = %s,
              descricao = %s
            where id = %s;
            update tags t
            set
              nome = %s  
              where id in (
                select id_tag
                from transacao_tag
                where id_transacao = %s
              ); 
          '''

          cur.execute(edit_query, (date, valor*100, descricao, id_transacao, tags, id_transacao, ))

        conn.commit()  

        flash('Updated successfully!')
        return redirect('/consultar')

      transacao = {
        'id': registro['id'],
        'date': registro['date'],
        'valor': registro['valor_em_cent']/100,
        'tag': registro['tag'],
        'descricao': registro['descricao'],
        'imgname': registro['imgname']
      }

      return render_template('index.html', transacao=transacao)


@app.route('/relatorio', methods=['GET'])
def relatorio_tag():

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432') 

  cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  date = request.args.get('date', None)

  if date:
    edit_date = date.split('-')

    cur.execute(''' 
      select count(1) "qtd_transacoes", sum(valor_em_cent) "valor_total", t.nome "tag"
      from transacoes tx
        inner join transacao_tag tg
          on tx.id = tg.id_transacao
        inner join tags t
          on t.id = tg.id_tag
      where extract(year FROM (select date)) = (%s)
        and extract(month FROM (select date)) = (%s)
      group by t.nome;
    ''',(edit_date[0], edit_date[1], )) 

    registros = cur.fetchall()

    transacoes = []

    cont_qtd_transacoes = 0
    cont_valor_total = 0

    for registro in registros:
      transacoes.append({
        'qtd': registro['qtd_transacoes'],
        'valor': registro['valor_total'],
        'tags': registro['tag'],
      })
      cont_qtd_transacoes += registro['qtd_transacoes']
      cont_valor_total += registro['valor_total']

  else:
    transacoes = None
    cont_qtd_transacoes = None
    cont_valor_total = None

  return render_template('relatorio.html', transacoes=transacoes, date=date, cont_qtd_transacoes=cont_qtd_transacoes, cont_valor_total=cont_valor_total)