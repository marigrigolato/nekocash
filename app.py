import uuid
import os
import psycopg2
import psycopg2.extras
from flask import Flask, redirect, render_template, request, send_from_directory, flash
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'some random string'
app.config['UPLOAD_FOLDER'] = 'static/files'

def allowed_file(filename):
  return '.' in filename and \
    filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
def index():

  if request.method == 'POST':

    connection = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

    cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    data = request.form['data']
    valor = request.form['valor']
    tags = request.form['tags']
    descricao = request.form['descricao']
    file = request.files['file']

    cursor.execute('''
      insert into transacoes (data, valor_em_cent, descricao)
      values (%s, %s, %s)
      returning id;   
    ''', (data, valor, descricao, ))      

    id_transacao = cursor.fetchone()
 
    if file and allowed_file(file.filename):

      filename = f"{uuid.uuid4()}{secure_filename(file.filename)}"

      cursor.execute('''
        insert into images (id_transacao, imgname)
        values (%s, %s)
      ''', (id_transacao['id'], filename, ))      

      file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

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
    ''', (id_transacao['id'], id_tag, ))       

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
    data = request.args.get('data', None)
    valor = request.args.get('valor', None)
    tags = request.args.getlist('tags', None)
    descricao = request.args.get('descricao', None)  

    insert_query = '''
      select tx.id, to_char(tx.data, 'DD/MM/YYYY'), tx.descricao, tx.valor_em_cent, t.nome tag, i.imgname
      from transacoes tx
        inner join transacao_tag tg
          on tx.id = tg.id_transacao
        inner join tags t
          on t.id = tg.id_tag
        full outer join images i 
          on tx.id = i.id_transacao  
      where 1=1
    '''

    parametros = []

    if data:
      insert_query += '''registros
        and tx.data = %s
      '''
      parametros.append(data)

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
        'data': registro['to_char'],
        'valor': registro['valor_em_cent'],
        'tags': registro['tag'],
        'descricao': registro['descricao']
      })    

    images = []

    for registro in registros:
      images.append({
        'imgname': registro['imgname']
      })    

    # print(images)
          
  return render_template('consultar.html', results_tags=results_tags, images=images, transacoes=transacoes, data=data, valor=valor, tags=tags, descricao=descricao)


@app.route('/uploads/<id_transacao>', methods=['GET'])
def download_file(id_transacao):

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cur = conn.cursor()

  cur.execute('''
    select imgname
    from images
    where id_transacao = %s;
  ''', (id_transacao, ))

  filename = cur.fetchall()
  
  file = [''.join(i) for i in filename] 

  return send_from_directory(app.config["UPLOAD_FOLDER"], file[0])


@app.route('/transacoes/<int:id_transacao>/excluir', methods=['POST'])
def delete_transacoes(id_transacao):

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cur = conn.cursor()

  cur.execute('''
    select imgname
    from images
    where id_transacao = %s;
  ''', (id_transacao, ))

  filename = cur.fetchall()

  file = [''.join(i) for i in filename] 

  os.remove(f'static/files/{file[0]}')

  delete_query = '''
    delete from transacao_tag where id_transacao = %s;
    delete from images where id_transacao = %s;
    delete from transacoes where id = %s;
  '''

  cur.execute(delete_query, (id_transacao, id_transacao, id_transacao, ))

  conn.commit()

  flash('Deleted successfully!')
  return redirect('/consultar', code = 303)


@app.route('/transacoes/edit/<int:id_transacao>', methods=['GET', 'POST'])
def edit_transacoes(id_transacao):

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  cur.execute('''
    select tx.id, tx.data, tx.descricao, tx.valor_em_cent, t.nome tag, i.imgname
    from transacoes tx
      inner join transacao_tag tg
        on tx.id = tg.id_transacao
      inner join tags t
        on t.id = tg.id_tag
      full outer join images i 
        on tx.id = i.id_transacao
    where tx.id = %s;
  ''',(id_transacao, ))

  registros = cur.fetchall()

  for registro in registros:

    if registro['id'] == id_transacao:

      if request.method == 'POST':
       
        name = registro['imgname']
        os.remove(f'static/files/{name}')

        data = request.form['data']
        valor = request.form['valor']
        tags = request.form['tags']
        descricao = request.form['descricao']
        file = request.files['file']

        if file and allowed_file(file.filename):

          filename = secure_filename(file.filename)
  
          cur.execute('''
            update images
            set
              imgname = %s
            where id_transacao = %s;
          ''', (filename, id_transacao, ))      

          file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))   
                  
          edit_query = '''
            update transacoes 
            set 
              data = %s,
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

          cur.execute(edit_query, (data, valor, descricao, id_transacao, tags, id_transacao, ))

          conn.commit()  

          flash('Updated successfully!')
          return redirect('/consultar')

      return render_template('index.html', transacao=registro)

@app.route('/relatorio', methods=['GET'])
def relatorio_tag():

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432') 

  cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  data = request.args.get('data', None)

  nova_data = data.split('-')

  cur.execute(''' 
    select tx.data, tx.valor_em_cent, t.nome tag
    from transacoes tx
      inner join transacao_tag tg
      on tx.id = tg.id_transacao
      inner join tags t
      on t.id = tg.id_tag
    where extract(year FROM (select data)) = (%s)
      and extract(month FROM (select data)) = (%s)
  ''',(nova_data[0], nova_data[1], )) 

  registros = cur.fetchall()

  transacoes = []

  for registro in registros:
    transacoes.append({
      'valor': registro['valor_em_cent'],
      'tags': registro['tag'],
    })   

  return render_template('relatorio.html', transacoes=transacoes, data=data)