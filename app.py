import os
import jinja2
import hashlib
import psycopg2
import psycopg2.extras
from datetime import datetime
from flask import Flask, redirect, render_template, request, flash, send_from_directory, session
from functools import wraps
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'some random string'
app.config['UPLOAD_FOLDER'] = 'static/files'


def login_required(func):
  @wraps(func)
  def decorated_function(*args, **kwargs):
    if not 'id' in session:
      return redirect('/login')
    return func(*args, **kwargs)
  return decorated_function


def allowed_file(filename):
  return '.' in filename and \
    filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def format_currency(value):
  if value is None:
    return ''
  if value == '':
    return ''
  return 'R${:,.2f}'.format(value)
jinja2.filters.FILTERS['format_currency'] = format_currency


def txs_unit_suffix(value):
  word = ' tx'
  if value > 1:
    word += 's'
  else:
    word += ''
  return f'{value}{word}'
jinja2.filters.FILTERS['txs_unit_suffix'] = txs_unit_suffix


def date_format(value):
  if value is None:
    return ''
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


@app.route('/login', methods=['GET', 'POST'])
def login():

  connection = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  if request.method == 'POST':

    email = request.form['email']
    password = request.form['password']
    if email == '' or password == '':
      return render_template('login.html', email=email, password=password)

    password_md5 = hashlib.md5(password.encode('utf-8')).hexdigest()

    cursor.execute ('''
      select id, password
      from users
      where email = (%s);
    ''', (email, ))

    row = cursor.fetchone()

    if row is None:
      # user not found
      return render_template('login.html', emailError='E-mail não cadastrado')

    id_user = row['id']

    if row['password'] == password_md5:
      session['id'] = id_user
      return redirect('/')
    else:
      return render_template('login.html', passwordError='Senha inválida')

  return render_template('login.html')


@app.route('/logout')
def logout():

  session.clear()

  return redirect('/login')


@app.route('/account', methods=['GET', 'POST'])
def account():

  connection = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  if request.method == 'POST':
    first_name = request.form['firstName']
    last_name = request.form['lastName']
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form['confirmPassword']

    if first_name == '' or email == '' or password == '' or confirm_password == '':
      return render_template('account.html', first_name=first_name, last_name=last_name, email=email, password=password, confirm_password=confirm_password, passwordError='Confirme sua senha')

    cursor.execute('''
      select email
      from users
      where email = (%s);
    ''', (email, ))

    search_for_users = cursor.fetchone()

    if search_for_users is None:
      if password == confirm_password:
        password_md5 = hashlib.md5(password.encode('utf-8')).hexdigest()
        cursor.execute('''
          insert into users (email, password, first_name, last_name)
          values (%s, %s, %s, %s)
          returning id;
        ''', (email, password_md5, first_name, last_name, ))
        row = cursor.fetchone()
        id_user = row['id']
        session['id'] = id_user
        connection.commit()
        return redirect('/')
      else:
        return render_template('account.html', first_name=first_name, last_name=last_name, email=email, password=password, confirm_password=confirm_password, validationErrors='As senhas inseridas não coincidem')
    else:
      return render_template('account.html', first_name=first_name, last_name=last_name, email=email, password=password, confirm_password=confirm_password, emailError='Este endereço de e-mail não está disponível. Escolha um endereço de e-mail diferente.')

  return render_template('account.html')

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():

  connection = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  cursor.execute('''
    select t.nome "tag"
    from tags t
    where t.id_user = (%s);
  ''', (session.get('id'), ))

  results_tags = cursor.fetchall()

  if request.method == 'POST':

    date = request.form['date']
    valor = request.form['valor']
    tags = request.form['tags']
    descricao = request.form['descricao']
    file = request.files['file']

    filename = secure_filename(file.filename)
    
    if date == '' or valor == '' or tags == '':
      return render_template('index.html', transacao={}, date=date, valor=valor, tags=tags)

    if not valor.replace('.', '').isdigit():
      return render_template('index.html', transacao={}, valor=False)

    valor = float(valor)

    cursor.execute('''
      insert into transacoes (date, valor_em_cent, descricao, imgname, id_user)
      values (%s, %s, %s, %s, %s)
      returning id;
    ''', (date, valor*100, descricao, filename, session.get('id')))

    row = cursor.fetchone()
    id_transacao = row['id']

    if file and allowed_file(file.filename):
      file.save(os.path.join(app.config['UPLOAD_FOLDER'], str(id_transacao)))

    cursor.execute('''
      select id, t.nome "tag"
      from tags t
      where t.nome = (%s) and t.id_user = (%s);
    ''', (tags, session.get('id'), ))

    results = cursor.fetchall()

    if results == []:

      cursor.execute('''
        insert into tags (nome, id_user)
        values (%s, %s)
        returning id;
      ''', (tags, session.get('id'), ))

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

  return render_template('index.html', transacao={}, results_tags=results_tags)


@app.route('/consultar', methods=['GET'])
@login_required
def consultar():

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

  cur.execute('''
    select t.nome "tag"
    from transacoes tx
      inner join transacao_tag tg
        on tx.id = tg.id_transacao
      inner join tags t
        on t.id = tg.id_tag
      inner join users u
        on u.id = tx.id_user and tx.id_user = (%s)
    group by t.nome
  ''', (session.get('id'), ))

  results_tags = cur.fetchall()

  if request.method == 'GET':
    date = request.args.get('date', None)
    valor = request.args.get('valor', None)
    tags = request.args.getlist('tags', None)
    descricao = request.args.get('descricao', None)

    insert_query = '''
      select tx.id, tx.date, tx.descricao, tx.valor_em_cent, tx.imgname, t.nome tag, u.id users
      from transacoes tx
        inner join transacao_tag tg
          on tx.id = tg.id_transacao
        inner join tags t
          on t.id = tg.id_tag
        inner join users u
          on u.id = tx.id_user and tx.id_user = (%s)
      where 1=1
    '''

    parametros = [session.get('id')]

    if date:
      insert_query += '''
        and tx.date = %s
      '''
      parametros.append(date)

    if valor:
      if not valor.replace('.', '').isdigit():
        return render_template('consultar.html', results_tags=results_tags, results=False, date=date, valor=valor, tags=tags, descricao=descricao)
      else:
        valor = float(valor)
        valor_em_cent = round(valor * 100)
        insert_query += '''
          and tx.valor_em_cent = %s
        '''
        parametros.append(valor_em_cent)

    if tags:
      insert_query += '''
        and t.nome in %s
      '''
      parametros.append(tuple(tags))

    if descricao:
      insert_query += '''
        and tx.descricao ilike %s
      '''
      parametros.append(f"%{descricao}%")

    cur.execute(insert_query, parametros)

    registros = cur.fetchall()

    if registros:

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
    else:
      if date or descricao or tags or valor:
        transacoes = []
      else:
        transacoes = None

  return render_template('consultar.html', results_tags=results_tags, transacoes=transacoes, date=date, valor=valor, tags=tags, descricao=descricao)


@app.route('/uploads/<id_transacao>', methods=['GET'])
@login_required
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
@login_required
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
@login_required
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
  ''', (id_transacao, ))

  registros = cur.fetchall()

  for registro in registros:

    if registro['id'] == id_transacao:

      if request.method == 'POST':

        date = request.form['date']
        valor = request.form['valor']
        tags = request.form['tags']
        descricao = request.form['descricao']
        file = request.files['file']

        filename = secure_filename(file.filename)

        if date == '' or valor == '' or tags == '':
          return render_template('index.html', transacao={}, date=date, valor=valor, tags=tags)

        if not valor.replace('.', '').isdigit():
          return render_template('index.html', transacao={}, valor=False)

        valor = float(valor)

        cur.execute('''
          select id, t.nome
          from tags t
          where t.nome = (%s) and t.id_user = (%s);
        ''', (tags, session.get('id'), ))

        results = cur.fetchall()

        if results == []:

          cur.execute('''
            insert into tags (nome, id_user)
            values (%s, %s)
            returning id;
          ''', (tags, session.get('id'), ))

          tag_row = cur.fetchone()

        else:
          tag_row = results[0]

        id_tag = tag_row['id']
        cur.execute('''
          update transacao_tag
          set
            id_tag = %s
            where id_transacao = %s
        ''', (id_tag, id_transacao, ))

        if file and allowed_file(file.filename):

          try:
            os.remove(f'static/files/{id_transacao}')
          except FileNotFoundError:
            pass

          file.save(os.path.join(app.config['UPLOAD_FOLDER'], str(id_transacao)))

          cur.execute('''
            update transacoes
            set 
              date = %s,
              valor_em_cent = %s,
              descricao = %s,
              imgname = %s 
            where id = %s
          ''', (date, valor*100, descricao, filename, id_transacao, ))

        else:

          cur.execute('''
            update transacoes
            set 
              date = %s,
              valor_em_cent = %s,
              descricao = %s
            where id = %s
          ''', (date, valor*100, descricao, id_transacao, ))

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
@login_required
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
        inner join users u
          on u.id = tx.id_user and tx.id_user = (%s)
      where extract(year FROM (select date)) = (%s)
        and extract(month FROM (select date)) = (%s)
      group by t.nome;
    ''', (session.get('id'), edit_date[0], edit_date[1], ))

    registros = cur.fetchall()

    transacoes = []

    cont_qtd_transacoes = 0
    cont_valor_total = 0

    for registro in registros:
      transacoes.append({
        'qtd': registro['qtd_transacoes'],
        'valor': registro['valor_total']/100,
        'tags': registro['tag'],
      })
      cont_qtd_transacoes += registro['qtd_transacoes']
      cont_valor_total += registro['valor_total']/100

  else:
    transacoes = None
    cont_qtd_transacoes = None
    cont_valor_total = None

  return render_template('relatorio.html', transacoes=transacoes, date=date, cont_qtd_transacoes=cont_qtd_transacoes, cont_valor_total=cont_valor_total)
