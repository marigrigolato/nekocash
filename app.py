import psycopg2
import psycopg2.extras
from flask import Flask, redirect, render_template, request, flash


app = Flask(__name__)
app.config['SECRET_KEY'] = 'some random string'


@app.route('/', methods=['GET', 'POST'])
def index():

  if request.method == 'POST':

    connection = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

    cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    data = request.form['data']
    valor = request.form['valor']
    tags = request.form['tags']
    descricao = request.form['descricao']

    cursor.execute('''
      insert into transacoes (data, valor_em_cent, descricao)
      values (%s, %s, %s)
      returning id;   
    ''', (data, valor, descricao,))      

    id_transacao = cursor.fetchone()

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
      ''', (tags,))

      tag_row = cursor.fetchone()
    else:
      tag_row = results[0]

    id_tag = tag_row['id']
    cursor.execute('''
      insert into transacao_tag (id_transacao, id_tag)
      values (%s, %s); 
    ''', (id_transacao['id'], id_tag,))

    connection.commit()

    flash('Transaction created successfully!')
    return redirect('/')

  return render_template('index.html', transacao={})


@app.route('/consultar', methods=['GET', 'POST'])
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
      select tx.id, to_char(tx.data, 'DD/MM/YYYY'), tx.descricao, tx.valor_em_cent, t.nome tag
      from transacoes tx
        inner join transacao_tag tg
          on tx.id = tg.id_transacao
        inner join tags t
          on t.id = tg.id_tag
      where 1=1
    '''

    parametros = []

    if data:
      insert_query += '''
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
    print(registros)
    transacoes = []

    for registro in registros:
      transacoes.append({
        'id': registro['id'],
        'data': registro['to_char'],
        'valor': registro['valor_em_cent'],
        'tags': registro['tag'],
        'descricao': registro['descricao']
      })    

  return render_template('consultar.html', results_tags=results_tags, transacoes=transacoes, data=data, valor=valor, tags=tags, descricao=descricao)


@app.route('/transacoes/<int:id_transacao>/excluir', methods=['POST'])
def delete_transacoes(id_transacao):

  conn = psycopg2.connect('dbname=nekocash user=marina password=123456 host=127.0.0.1 port=5432')

  cur = conn.cursor()

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

  select_query = '''
    select tx.id, tx.data, tx.descricao, tx.valor_em_cent, t.nome tag
    from transacoes tx
      inner join transacao_tag tg
        on tx.id = tg.id_transacao
      inner join tags t
        on t.id = tg.id_tag
    where tx.id = %s;
  '''

  cur.execute(select_query, (id_transacao, ))

  registros = cur.fetchall()

  for registro in registros:

    if registro['id'] == id_transacao:

      if request.method == 'POST':
        data = request.form['data']
        valor = request.form['valor']
        tags = request.form['tags']
        descricao = request.form['descricao']

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