# coding: utf-8
import flask
#sqlalchemy
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func, select
from sqlalchemy import desc, asc
#custom config
import config
from json import dumps as json_dumps
import os
import uuid

from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form.upload import FileUploadField, ImageUploadField

from flask_bcrypt import Bcrypt

import random
from datetime import datetime

from werkzeug.utils import secure_filename
from wtforms.fields import TextField
from werkzeug.exceptions import HTTPException

from flask_ckeditor import CKEditor, CKEditorField

from flask_basicauth import BasicAuth

from PIL import Image as ProcessImage

from flask_admin.model import typefmt
from datetime import date

from flask_sessionstore import Session
from flask_session_captcha import FlaskSessionCaptcha

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


app = flask.Flask(__name__)

bcrypt = Bcrypt(app)

ckeditor = CKEditor(app)

#bcrypt = Bcrypt(app)
app.secret_key = config.secret_key

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + config.db_file
#app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1qL6hQQ6x8QDi9rr@localhost/macos'
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
#app.config['SQLALCHEMY_POOL_SIZE'] = 30
app.config['THUMBNAIL_FOLDER'] = config.THUMBNAIL_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 80 * 1024 * 1024 #80mb max
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp'])
db = SQLAlchemy(app)

app.config["SECRET_KEY"] = uuid.uuid4()
app.config['CAPTCHA_ENABLE'] = True
app.config['CAPTCHA_LENGTH'] = 5
app.config['CAPTCHA_WIDTH'] = 160
app.config['CAPTCHA_HEIGHT'] = 60
app.config['SESSION_TYPE'] = 'sqlalchemy'
session = Session(app)
captcha = FlaskSessionCaptcha(app)
session.app.session_interface.db.create_all()

app.config['BASIC_AUTH_USERNAME'] = config.login
app.config['BASIC_AUTH_PASSWORD'] = config.password

basic_auth = BasicAuth(app)

def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Setting(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	name = db.Column(db.String())
	value = db.Column(db.String())

	def get_settings():
		as_dict = {}
		for i in Setting.query.all():
			as_dict[i.name] = i.value

		return as_dict

	def __repr__(self):
		return self.name

class Manufacture(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(50), nullable=False)
	goods = db.relationship('Good', backref='manufacture', lazy=True)

	def __repr__(self):
		return self.name

class Review(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	user_name = db.Column(db.String(50), nullable=False)
	date = db.Column(db.DateTime, nullable=False, default=datetime.now())
	comment = db.Column(db.String())
	rate_id = db.Column(db.Integer, db.ForeignKey('rate_num.id'), nullable=False)
	good_id = db.Column(db.Integer, db.ForeignKey('good.id'))
	is_published = db.Column(db.Boolean(), default=True)

	def __repr__(self):
		return self.date

class Rate_num(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	rate = db.Column(db.Integer, nullable=False)
	reviews = db.relationship('Review', backref='rating', lazy=True)

	def __repr__(self):
		return str(self.rate)

class Good(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	name = db.Column(db.String(), nullable=False)
	model = db.Column(db.String())
	url = db.Column(db.String(), nullable=False)
	details = db.Column(db.String())
	price = db.Column(db.Integer, nullable=False)
	price_wo = db.Column(db.Integer, nullable=True)
	images = db.relationship('Image', backref='good', lazy=True)
	cat_id = db.Column(db.Integer, db.ForeignKey('category.id'))
	in_stock = db.Column(db.Boolean(), default=True)
	by_request = db.Column(db.Boolean(), default=False)
	manufacture_id = db.Column(db.Integer, db.ForeignKey('manufacture.id'),
		nullable=False)
	date = db.Column(db.DateTime, nullable=False, default=datetime.now())
	orders = db.relationship('Orders', backref='good', cascade="all,delete", lazy=True)
	reviews = db.relationship('Review', backref='good', lazy=True)
	sales = db.relationship('Sale', backref='good', lazy=True)
	top_goods = db.relationship('Top_good', backref='good', lazy=True)

	@hybrid_property
	def avg_rating(self):
		if self:
			return int(self.get_avg_ratig())

	@avg_rating.expression
	def avg_rating(cls):
		return (select([func.avg(Review.rate_id)])
				.where(Review.good_id == cls.id))

	def get_rev_len(self):
		reviews = []
		for review in self.reviews:
			if review.is_published:
				reviews.append(review)

		return len(reviews)

	def get_avg_ratig(self):
		rates = []
		for review in self.reviews:
			if review.is_published:
				rates.append(review.rating.rate)
		try:
			return round(sum(rates) / len(rates))
		except ZeroDivisionError:
			return 0

	def __repr__(self):
		return self.name

	def as_dict(self):
		as_dict = {}
		as_dict['name'] = self.name
		as_dict['url'] = self.url
		as_dict['cat'] = self.category.name
		if self.sales:
			as_dict['price'] = self.price - (self.price * self.sales[0].sale / 100)
		else:
			as_dict['price'] = self.price 

		try:
			as_dict['img'] = app.config['THUMBNAIL_FOLDER'] + '/' + self.images[0].file_name
		except Exception as e:
			print(e)
			as_dict['img'] = ''

		return as_dict

class Image(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	good_id = db.Column(db.Integer, db.ForeignKey('good.id'))
	file_name = db.Column(db.String())

	def __repr__(self):
		return self.file_name

class Category(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	name = db.Column(db.String)
	goods = db.relationship('Good', backref='category', lazy=True)
	sales = db.relationship('Sale', backref='category', lazy=True)

	def get_max_price(self):
		try:
			max_p = self.goods[0].price
		except IndexError:
			return flask.abort(404)
		for good in self.goods:
			if good.price > max_p:
				max_p = good.price
		return max_p

	def get_min_price(self):
		try:
			min_p = self.goods[0].price
		except IndexError:
			return flask.abort(404)
		for good in self.goods:
			if good.price < min_p:
				min_p = good.price
		return min_p

	def __repr__(self):
		return self.name

class Order(db.Model):

	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	goods = db.relationship('Orders', backref='order', cascade="all,delete", lazy=True)
	address = db.Column(db.String())
	comment = db.Column(db.String())
	phone = db.Column(db.String())
	name = db.Column(db.String())
	email = db.Column(db.String()) 
	shipping_method = db.Column(db.String())
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	date = db.Column(db.DateTime, default=datetime.now())
	summ = db.Column(db.Integer)

	def __repr__(self):
		return self.address

	def price(self):
		summ = 0
		for good in self.goods:
			summ += good.good.price
		return summ

class Orders(db.Model):
	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
	good_id = db.Column(db.Integer, db.ForeignKey('good.id'),
		nullable=False)
	amount = db.Column(db.Integer)

	def price(self):
		if self.good.sales:
			price = (self.good.price - (self.good.price * self.good.sales[0].sale)/100) * self.amount
		else:
			price = self.good.price * self.amount
		return price

	def __repr__(self):
		return str(self.good) + ' - ' + str(self.amount) + ' шт. ' + str(self.price()) + ' грн.'

class Sale(db.Model):
	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	good_id = db.Column(db.Integer, db.ForeignKey('good.id'),
		nullable=False)
	cat_id = db.Column(db.Integer, db.ForeignKey('category.id'))
	sale = db.Column(db.Integer, nullable=False, default=10)
	end_date = db.Column(db.DateTime, nullable=False, default=datetime.now())

class Top_good(db.Model):
	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	good_id = db.Column(db.Integer, db.ForeignKey('good.id'),
		nullable=False)

class InfoPage(db.Model):
	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	name = db.Column(db.String())
	content = db.Column(db.String())

	def __repr__(self):
		return self.name

favorites = db.Table('favorites',
	db.Column('good_id', db.Integer, db.ForeignKey('good.id'), primary_key=True),
	db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class User(db.Model):
	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	email = db.Column(db.String())
	password = db.Column(db.String())
	name = db.Column(db.String())
	phone = db.Column(db.String())
	post = db.Column(db.String())
	region=db.Column(db.String())
	city=db.Column(db.String())
	address=db.Column(db.String())
	favorites = db.relationship('Good', secondary=favorites, lazy='subquery')
	orders = db.relationship('Order', backref='user', lazy=True)

	def __repr__(self):
		return self.name

class Contact_us(db.Model):
	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	name = db.Column(db.String())
	email = db.Column(db.String())
	text = db.Column(db.String())

	def __repr__(self):
		return 'Сообщение от' + self.name

class Slider(db.Model):
	id = db.Column(db.Integer, primary_key=True, autoincrement=True)
	title = db.Column(db.String())
	text = db.Column(db.String())
	img = db.Column(db.String())
	url = db.Column(db.String())

	def __repr__(self):
		return self.title

#db.create_all()

#------------------/database classes/---------------------------

#------------------<flask_admin>--------------------------------

class AuthException(HTTPException):
	def __init__(self, message):
		super().__init__(message, flask.Response(
			message, 401,
			{'WWW-Authenticate': 'Basic realm="Login Required"'}
		))

#restict access to /admin index
class MyAdminIndexView(AdminIndexView):

	def is_accessible(self):
		if not basic_auth.authenticate():
			raise AuthException('Not authenticated. Refresh the page.')
		else:
			return True

	def inaccessible_callback(self, name, **kwargs):
		return flask.redirect(basic_auth.challenge())

	def is_visible(self):
		return False

def prefix_name(obj=None, file_data=''):
	hash = random.getrandbits(128)
	ext = file_data.filename.split('.')[-1]
	path = '%s.%s' % (hash, ext)
	return path

def thumb_name(file_data):
	#name = file_data.split("/")
	return os.path.join('thumbnails', file_data)

def date_format(view, value):
	return value.strftime('%d.%m.%Y')

datetime_formatter = dict(typefmt.BASE_FORMATTERS)
datetime_formatter.update({
	type(None): typefmt.null_formatter,
	date: date_format
})

class ReviewView(ModelView):
	column_type_formatters = datetime_formatter
	column_type_formatters_detail = datetime_formatter
	column_type_formatters_export = datetime_formatter

	form_args = dict(
		date=dict(format='%d.%m.%Y') # changes how the input is parsed by strptime (12 hour time)
	)
	form_widget_args = dict(
		date={
			'data-date-format': u'dd.mm.yyyy'
		} # changes how the DateTimeField displays the time
	)

#list of users in admin
class DefView(ModelView):
	column_display_pk = True

	form_overrides = {
		'img': ImageUploadField
	}

	#form_excluded_columns = ('goods')

	def is_accessible(self):
		if not basic_auth.authenticate():
			raise AuthException('Not authenticated. Refresh the page.')
		else:
			return True

	def inaccessible_callback(self, name, **kwargs):
		return flask.redirect(basic_auth.challenge())

	form_args = {
		'img': {
			'label': 'Изображение',
			'base_path': 'static/uploads',
			'allow_overwrite': True,
			'namegen': prefix_name,
			'max_size': (700,560,True),
			'thumbnail_size': (256,256, True),
			'thumbgen' : thumb_name
		}
	}

class SettingsView(ModelView): #setting
	form_extra_fields = {
		'file': FileUploadField('file', base_path = app.config['UPLOAD_FOLDER'], namegen = prefix_name)
	}

	form_widget_args = {
		'name': {
			'readonly': False
		},
	}

	def is_accessible(self):
		if not basic_auth.authenticate():
			raise AuthException('Not authenticated. Refresh the page.')
		else:
			return True

	def inaccessible_callback(self, name, **kwargs):
		return flask.redirect(basic_auth.challenge())

	def on_model_change(self, form, Setting, is_created=False):
		if not form.value.data:
			Setting.value = os.path.join(app.config['UPLOAD_FOLDER'], form.file.data.filename)

class SaleView(ModelView):
	form_excluded_columns = ('category')
	column_labels = dict(sale='Скидка %', end_date = 'Дата окончания акции', good='Товар')

	def on_model_change(self, form, Sale, is_created=False):
		Sale.cat_id = Good.query.get(form.good.data.id).cat_id

	def is_accessible(self):
		if not basic_auth.authenticate():
			raise AuthException('Not authenticated. Refresh the page.')
		else:
			return True

	def inaccessible_callback(self, name, **kwargs):
		return flask.redirect(basic_auth.challenge())

class GoodView(ModelView): #goods
	column_display_pk = True
	form_display_pk = True
	form_extra_fields = {
		'temp_field': TextField('Загрузить изображение')
	}

	form_excluded_columns = ('orders')
	column_exclude_list = ('details', 'specs', 'page_specs')

	column_labels = dict(name='Наименование', url='Url', details='Описание', price='Цена', images='Изображения', date='Дата выхода', manufacture='Производитель', in_stock='В наличии', category = 'Категория', model = 'Модель', by_request='Под заказ')

	form_columns = ('images', 'temp_field', 'category', 'name', 'url', 'date', 'details', 'in_stock', 'by_request', 'manufacture', 'price', 'model')

	def is_accessible(self):
		if not basic_auth.authenticate():
			raise AuthException('Not authenticated. Refresh the page.')
		else:
			return True

	def inaccessible_callback(self, name, **kwargs):
		return flask.redirect(basic_auth.challenge())

	form_overrides = dict(details=CKEditorField, page_specs=CKEditorField)

	create_template = 'admin_edit.html'
	edit_template = 'admin_edit.html'

class PageView(ModelView):
	form_extra_fields = {
		'temp_field': TextField('Загрузить файл')
	}

	form_overrides = dict(content=CKEditorField)

	create_template = 'page_admin_edit.html'
	edit_template = 'page_admin_edit.html'

	def is_accessible(self):
		if not basic_auth.authenticate():
			raise AuthException('Not authenticated. Refresh the page.')
		else:
			return True

	def inaccessible_callback(self, name, **kwargs):
		return flask.redirect(basic_auth.challenge())

class OrderView(ModelView):
	column_labels = dict(goods='Товары', address='Адрес', comment='Комментарий', phone='Телефон', name='ФИО', shipping_method='Способ доставки', date='Время заказа', summ='Сумма (грн.)', user = 'Пользователь')

	form_columns = ('goods', 'summ', 'name', 'address', 'phone', 'email', 'comment', 'date', 'shipping_method', 'user')

	column_list = ('goods', 'summ', 'address', 'phone', 'email')

	def is_accessible(self):
		if not basic_auth.authenticate():
			raise AuthException('Not authenticated. Refresh the page.')
		else:
			return True

	def inaccessible_callback(self, name, **kwargs):
		return flask.redirect(basic_auth.challenge())

class SliderView(ModelView):

	form_overrides = {
		'img': FileUploadField
	}

	column_list = ('title', 'text')

	def is_accessible(self):
		if not basic_auth.authenticate():
			raise AuthException('Not authenticated. Refresh the page.')
		else:
			return True

	def inaccessible_callback(self, name, **kwargs):
		return redirect(basic_auth.challenge())

	form_args = {
		'img': {
			'label': 'Изображение',
			'base_path': 'static',
			'allow_overwrite': True,
			'namegen': prefix_name,
			'thumbnail_size': (256,256, True),
			'thumbgen' : thumb_name
		}
	}

#initialize admin views
admin = Admin(app, name='Панель управления', template_mode='bootstrap3', index_view=MyAdminIndexView(), url='/')
admin.add_view(SettingsView(Setting, db.session, 'Настройки', url='/admin/sgs'))
admin.add_view(DefView(Slider, db.session, 'Slider', url='/admin/slider'))
admin.add_view(OrderView(Order, db.session, 'Заказы', url='/admin/orders'))
admin.add_view(SaleView(Sale, db.session, 'Акции', url='/admin/sales'))
admin.add_view(PageView(InfoPage, db.session, 'Страницы', url='/admin/pages'))
admin.add_view(DefView(Category, db.session, 'Категории', url='/admin/categories', category='Товары'))
admin.add_view(DefView(Manufacture, db.session, 'Производитель', url='/admin/manufacture', category='Товары'))
admin.add_view(ReviewView(Review, db.session, 'Отзывы', url='/admin/reviews', category='Товары'))
admin.add_view(DefView(Top_good, db.session, 'Хиты продаж', url='/admin/top_goods', category='Товары'))
admin.add_view(GoodView(Good, db.session, 'Товары', url='/admin/goods', category='Товары'))
admin.add_view(DefView(Contact_us, db.session, 'Связаться с нами', url='/admin/contact_us', category='Дополнительно'))
#---------------------/flask_admin/---------------------

class Cart():

	def __repr__():
		order_list = []

		if Cart.get():
			for good in Cart.get():
				good_model = Good.query.get(good['good_id'])
				if good_model:
					if good_model.sales:
						price = (good_model.price - (good_model.price * good_model.sales[0].sale)/100) * int(good['amount'])
					else:
						price = good_model.price * int(good['amount'])


					order_list.append({'good':good_model,
						'good_id':good['good_id'],
						'amount':good['amount'],
						'price': price})


		return order_list

	def get():
		if 'goods_in_cart' in flask.session:
			return flask.session['goods_in_cart']
		else:
			return False

	def update(cart):
		#self.get() = cart
		flask.session['goods_in_cart'] = cart


	def get_amount():
		amount = 0

		if Cart.get(): #if has cart in cookies
			for good in Cart.get():
				try:
					amount += good['amount']
				except:
					pass

		return amount

	def update_good():
		goods = []
		summ = 0

		update_good = flask.request.json

		if Cart.get():
			for good in Cart.get():
				good_model = Good.query.get(good['good_id'])
				if int(update_good['good_id']) == int(good['good_id']):
					update_good['price'] = good_model.price * int(update_good['amount'])

					good = update_good
				goods.append(good)

				summ += good_model.price * int(good['amount'])

		Cart.update(goods)

		return json_dumps({'success': True, 'cart': Cart.get(), 'updated_good':update_good, 'summ':summ}), 200, {'ContentType':'application/json'} 

	def pop_good():
		good_id = flask.request.args.get("id")
		goods = []

		if Cart.get():
			for good in Cart.get():
				if str(good["good_id"]) != str(good_id):
					goods.append(good)

		Cart.update(goods)
		#return flask.redirect(flask.url_for("cart"))
		print(flask.request.args)
		return flask.redirect('/'+flask.request.args.get('backurl'))

	def add_good():
		new_good = flask.request.json
		new_good['amount'] = int(new_good['amount'])
		good_model = Good.query.get(new_good['good_id'])
		if good_model.sales:
			new_good['price'] = (good_model.price - (good_model.price * good_model.sales[0].sale)/100) * int(new_good['amount'])
		else:
			new_good['price'] = good_model.price * int(new_good['amount'])
		#new_good['price'] = new_good['amount'] * Good.query.get(new_good['good_id']).price
		new_good['model'] = Good.query.get(new_good['good_id']).as_dict()

		goods = []
		temp = []

		if Cart.get(): #if has cart in cookies
			for good in Cart.get(): #get every item from cart in cookies
				if new_good['good_id'] == good['good_id']: #and if this item equals to new item
					good['amount'] += new_good['amount'] #just add amount but don't create new item
					good_model = Good.query.get(good['good_id'])
					if good_model.sales:
						good['price'] = (good_model.price - (good_model.price * good_model.sales[0].sale)/100) * int(good['amount'])
					else:
						good['price'] = good_model.price * int(good['amount'])
				good['model'] =  Good.query.get(good['good_id']).as_dict()
				goods.append(good) #and add to list of goods
				temp.append(good['good_id']) #add id to temp list of id's
				#this needed to check that there's element in cart
				#and if it's not add it

			try:
				temp.index(new_good['good_id']) #trying to find new element in cart
			except:
				goods.append(new_good) #if it's not - add it
		else: #if cart is empty then add first element
			goods.append(new_good)

		Cart.update(goods) #update cart in cookies
		
		return json_dumps({'success': True, 'cart': Cart.get(),'good_amount': Cart.get_amount()}), 200, {'ContentType':'application/json'} 

	def confirm():
		f = flask.request.form.to_dict(flat=False)
		if flask.request.method == "POST":
			print(f)
			if captcha.validate():
				if f['shipping_address_city'][0] == '' or f['shipping_address'][0] == '' or f['telephone'][0] == '' or f['firstname'][0] == '':
					flask.flash('Адрес, имя или номер телефона не заполнены. Попробуйте снова.')
					return flask.redirect(flask.url_for("simplecheckout"))
				else:
					new_order = Order()
					new_order.address ='Область: '+ str(f['country'][0]) + '; Город: ' + str(f['shipping_address_city'][0]) + '; Адрес или отделение НП: ' + str(f['shipping_address'][0])
					new_order.phone = f['telephone'][0]
					new_order.name = f['firstname'][0]
					comment = ''
					method = ''
					try:
						new_order.comment = f['comment'][0]
						comment = f['comment'][0]
						new_order.email = f['email'][0]
						new_order.shipping_method = f['shipping_method'][0] +'; '+ f['payment_method'][0] + '; '+ f['card_data'][0]
						method = f['payment_method'][0]
						date = datetime.now()
					except:
						pass

					if 'user_id' in flask.request.args:
						new_order.user_id = flask.request.args.get('user_id', type=int)

					summ = 0
					good_names = []

					db.session.add(new_order)
					if Cart.get():
						for good in Cart.__repr__():
							good_order = Orders(good_id = int(good['good_id']), amount = int(good['amount']))
							summ += int(good['amount']) * int(good['price'])
							good_names.append(Good.query.get(int(good['good_id'])).name)
							new_order.goods.append(good_order)
							db.session.add(good_order)

					new_order.summ = summ
					db.session.flush()
					order_id = new_order.id

					db.session.commit()

					flask.session.pop('goods_in_cart')


					message = MIMEMultipart("alternative")
					message["Subject"] = "Новый заказ № %s на сайте %s"%(str(order_id), flask.request.host)
					message["From"] = Setting.query.filter_by(name = 'email_from').first().value
					message["To"] = Setting.query.filter_by(name = 'email_to').first().value

					# Create the plain-text and HTML version of your message
					text = """\
					Новый заказ на сайте %s:
					Товары: %s
					<br>
					Сумма: %d
					<br>
					ФИО: %s
					<br>
					Телефон: %s
					<br>
					Город: %s
					<br>
					Отделение: %s
					<br>
					Способ оплаты: %s
					<br>
					Комментарий: %s
					<br>
					Ссылка: %s"""%(flask.request.host,', '.join(good_names), summ, f['firstname'][0], f['telephone'][0], f['shipping_address_city'][0], f['shipping_address'][0], method, comment, 'appstore.in.ua/admin/orders/edit/?id='+str(order_id))

					html = """\
					<html>
					  <body>
					  	<p>
					    Новый заказ на сайте %s:
					    </p>
					    <p>
							Товары: %s
							<br>
							Сумма: %d
							<br>
							ФИО: %s
							<br>
							Телефон: %s
							<br>
							Город: %s
							<br>
							Отделение: %s
							<br>
							Способ оплаты: %s
							<br>
							Комментарий: %s
							<br>
							<a href='%s'>Ссылка на заказ в админке</a>
					    </p>
					  </body>
					</html>
					"""%(flask.request.host,', '.join(good_names), summ, f['firstname'][0], f['telephone'][0], f['shipping_address_city'][0], f['shipping_address'][0], method, comment, 'appstore.in.ua/admin/orders/edit/?id='+str(order_id))

					# Turn these into plain/html MIMEText objects
					part1 = MIMEText(text, "plain")
					part2 = MIMEText(html, "html")

					# Add HTML/plain-text parts to MIMEMultipart message
					# The email client will try to render the last part first
					message.attach(part1)
					message.attach(part2)

					try:
						server = smtplib.SMTP_SSL(Setting.query.filter_by(name = 'email_smtp').first().value, Setting.query.filter_by(name = 'email_port').first().value)
						server.login(Setting.query.filter_by(name = 'email_login').first().value, Setting.query.filter_by(name = 'email_password').first().value)
						server.sendmail(Setting.query.filter_by(name = 'email_from').first().value, Setting.query.filter_by(name = 'email_to').first().value, message.as_string())         
						print("Successfully sent email")
					except Exception as e:
						print("Error: unable to send email")
						print(e)

					print(f)
					flask.session['order_id'] = order_id
					#flask.session['rand_order_id'] = random.getrandbits(64)
					return flask.redirect('/#order_done')
			else:
				flask.flash('Код введен неверно. Попробуйте снова.')
				return flask.redirect(flask.url_for("simplecheckout"))


	def render():
		summ = 0

		if 'goods_in_cart' in flask.session:
			for good in flask.session['goods_in_cart']:
				good_model = Good.query.get(good['good_id'])
				if good_model:
					try:
						if good_model.sales:
							summ += (good_model.price - (good_model.price * good_model.sales[0].sale)/100) * int(good['amount'])
						else:
							summ += good_model.price * int(good['amount'])
					except:
						pass

		
		return flask.render_template("cart.html",
			pages=InfoPage.query.all(),
			categories = Category.query.all(),
			settings = Setting.get_settings(), 
			cart = Cart,
			summ = summ,
			cabinet=Cabinet)

	def simplecheckout():
		summ = 0

		if 'goods_in_cart' in flask.session:
			for good in flask.session['goods_in_cart']:
				good_model = Good.query.get(good['good_id'])
				if good_model:
					try:
						if good_model.sales:
							summ += (good_model.price - (good_model.price * good_model.sales[0].sale)/100) * int(good['amount'])
						else:
							summ += good_model.price * int(good['amount'])
					except:
						pass

		return flask.render_template("simplecheckout.html",
			pages=InfoPage.query.all(),
			categories = Category.query.all(),
			settings = Setting.get_settings(), 
			cart = Cart,
			summ = summ,
			cabinet=Cabinet)


app.add_url_rule('/simplecheckout', 'simplecheckout', Cart.simplecheckout, methods=["GET","POST"])
app.add_url_rule('/cart', 'cart', Cart.render, methods=["GET","POST"])
app.add_url_rule('/update_good_cart', 'update_good_cart', Cart.update_good, methods=["GET","POST"])
app.add_url_rule('/pop_cart_good', 'pop_cart_good', Cart.pop_good, methods=["GET","POST"])
app.add_url_rule('/add_good_cart', 'add_good_cart', Cart.add_good, methods=["GET","POST"])
app.add_url_rule('/confirm_order', 'add_good_cartconfirm_order', Cart.confirm, methods=["GET","POST"])

#---------------------/cart/----------------------------------------

#---------------------<cabinet>----------------------------------------

class EmptyUser():
	email = ''
	password = ''
	name = ''
	phone = ''
	post = ''
	region=''
	city=''
	address=''

class Cabinet():

	def user():
		if Cabinet.get():
			return User.query.get(Cabinet.get())
		else:
			return EmptyUser

	def get():
		if 'logged' in flask.session:
			print(flask.session['logged'])
			return flask.session['logged']
		else:
			return False

	def update(user_id):
		flask.session['logged'] = user_id

	def register():

		if flask.request.method == 'POST':
			f = flask.request.form.to_dict(flat=False)

			if [''] in f.values(): #if there's any empty field
				flask.flash("Не все поля заполнены")
				return flask.redirect(flask.url_for("register"))
			elif not captcha.validate():
				flask.flash("Код введен неверно. Попробуйте снова")
				return flask.redirect(flask.url_for("register"))
			else:
				if User.query.filter_by(email = f["email"][0]).first():
					flask.flash("Пользователь с таким именем уже существует")
					return flask.redirect(flask.url_for("register"))
				else:
					new_user = User(post = str(f['address'][0]), phone = str(f['telephone'][0]), name = str(f['firstname'][0]), email = str(f['email'][0]),password = bcrypt.generate_password_hash(str(f["password"][0])))
					db.session.add(new_user)
					db.session.commit()

					Cabinet.update(new_user.id)

					return flask.redirect(flask.url_for('my-account'))
		else:
			return flask.render_template("register.html",
				pages=InfoPage.query.all(),
				categories = Category.query.all(),
				settings = Setting.get_settings(), 
				cart = Cart,
				cabinet=Cabinet)

	def login():
		if flask.request.method == 'POST':
			email = flask.request.form["email"] 
			password = flask.request.form["password"]
			user_data = User.query.filter_by(email = email).first()

			if user_data is not None:
				if bcrypt.check_password_hash(user_data.password, str(password)):
					Cabinet.update(user_data.id)
					return flask.redirect(flask.url_for("my-account"))
				else:
					flask.flash("Wrong password. Try again")
			else:
				flask.flash("Wrong Login. Try again")

		return flask.render_template("login.html",
			pages=InfoPage.query.all(),
			categories = Category.query.all(),
			settings = Setting.get_settings(), 
			cart = Cart,
			cabinet=Cabinet)

	def exit():
		flask.session.pop('logged') #clear session when user log out
		return flask.redirect(flask.url_for("index"))

	def my_account():
		if Cabinet.get():
			return flask.render_template("my_account.html",
				pages=InfoPage.query.all(),
				categories = Category.query.all(),
				settings = Setting.get_settings(), 
				cart = Cart,
				cabinet = Cabinet)
		else:
			return flask.redirect(flask.url_for("login"))

	def edit_account():
		if not Cabinet.get():
			return flask.redirect(flask.url_for('login'))
		else:
			if flask.request.method == 'POST':
				f = flask.request.form.to_dict(flat=False)

				if [''] in f.values(): #if there's any empty field
					flask.flash("Не все поля заполнены")
					return flask.redirect(flask.url_for("edit_account"))
				else:
					if f["email"][0] != Cabinet.user().email:
						if User.query.filter_by(email = f["email"][0]).first():
							flask.flash("Пользователь с таким email уже существует")
							return flask.redirect(flask.url_for("edit_account"))
						else:
							User.query.get(Cabinet.get()).email = f["email"][0]
							db.session.commit()

					if f["firstname"][0] != Cabinet.user().name:
						User.query.get(Cabinet.get()).name = f["firstname"][0]
						db.session.commit()

					if f["telephone"][0] != Cabinet.user().phone:
						User.query.get(Cabinet.get()).phone = f["telephone"][0]
						db.session.commit()

			return flask.render_template("edit-account.html",
				pages=InfoPage.query.all(),
				categories = Category.query.all(),
				settings = Setting.get_settings(), 
				cart = Cart,
				cabinet = Cabinet)

	def add_good_wishlist():
		if Cabinet.get():
			new_good = flask.request.json
			user = User.query.get(Cabinet.get())
			user.favorites.append(Good.query.get(new_good['good_id']))
			db.session.add(user)
			db.session.commit()

			return json_dumps({'success': True}), 200, {'ContentType':'application/json'}
		else:
			return flask.redirect(flask.url_for('login'))

	def wishlist():
		if not Cabinet.get():
			return flask.redirect(flask.url_for('login'))
		else:
			return flask.render_template("wishlist.html",
				pages=InfoPage.query.all(),
				categories = Category.query.all(),
				settings = Setting.get_settings(), 
				cart = Cart,
				cabinet = Cabinet)

	def remove_wishlist():
		good_id = flask.request.args.get('id')
		user = User.query.get(Cabinet.get())
		user.favorites.remove(Good.query.get(good_id))
		db.session.commit()
		flask.flash('Успешно удалено из избранного')

		return flask.redirect(flask.url_for('wishlist'))

	def add_good_compare():
		new_good = flask.request.json
		if 'compare_goods' not in flask.session:
			flask.session['compare_goods'] = [new_good['good_id']]
		else:
			goods = flask.session['compare_goods']
			if new_good['good_id'] not in goods:
				goods.append(new_good['good_id'])
			flask.session['compare_goods'] = goods

		return json_dumps({'success': True, 'compare_goods': flask.session['compare_goods']}), 200, {'ContentType':'application/json'}

	def compare():
		goods = []
		if 'compare_goods' in flask.session:
			for good_id in flask.session['compare_goods']:
				goods.append(Good.query.get(good_id))

		return flask.render_template("compare.html",
				pages=InfoPage.query.all(),
				categories = Category.query.all(),
				settings = Setting.get_settings(), 
				cart = Cart,
				goods = goods,
				cabinet = Cabinet)

	def remove_good_compare():
		good_id = flask.request.args.get('good_id', type=int)

		goods = flask.session['compare_goods']
		for num, id in enumerate(goods):
			if good_id == id:
				goods.pop(num)

		flask.session['compare_goods'] = goods

		return flask.redirect(flask.url_for('compare'))


	def change_password():
		if not Cabinet.get():
			return flask.redirect(flask.url_for('login'))
		else:
			if flask.request.method == 'POST':
				f = flask.request.form.to_dict(flat=False)
				if [''] in f.values(): #if there's any empty field
					flask.flash("Не все поля заполнены")
					return flask.redirect(flask.url_for("change_password"))
				else:
					if len(f['password'][0]) < 4:
						flask.flash("Длина пароля должна быть не менее 4 символов")
						return flask.redirect(flask.url_for("change_password"))
					else:
						if f['password'][0] == f['confirm'][0]:
							User.query.get(Cabinet.get()).password = bcrypt.generate_password_hash(str(f["password"][0]))
							db.session.commit()
						else:
							flask.flash("Пароли не совпадают")
							return flask.redirect(flask.url_for("change_password"))

		return flask.render_template("change_password.html",
				pages=InfoPage.query.all(),
				categories = Category.query.all(),
				settings = Setting.get_settings(), 
				cart = Cart,
				cabinet = Cabinet)

	def edit_address():
		if not Cabinet.get():
			return flask.redirect(flask.url_for('login'))
		else:
			if flask.request.method == 'POST':
				f = flask.request.form.to_dict(flat=False)
				User.query.get(Cabinet.get()).region = str(f['country'][0])
				User.query.get(Cabinet.get()).city = str(f['shipping_address_city'][0])
				User.query.get(Cabinet.get()).address = str(f['shipping_address'][0])
				User.query.get(Cabinet.get()).name=f['firstname'][0]
				db.session.commit()

			return flask.render_template("edit_address.html",
					pages=InfoPage.query.all(),
					categories = Category.query.all(),
					settings = Setting.get_settings(), 
					cart = Cart,
					cabinet = Cabinet)

	def history():
		if not Cabinet.get():
			return flask.redirect(flask.url_for('login'))
		else:
			return flask.render_template("history.html",
					pages=InfoPage.query.all(),
					categories = Category.query.all(),
					settings = Setting.get_settings(), 
					cart = Cart,
					cabinet = Cabinet)

	def downloads():
		if not Cabinet.get():
			return flask.redirect(flask.url_for('login'))
		else:
			return flask.render_template("downloads.html",
					pages=InfoPage.query.all(),
					categories = Category.query.all(),
					settings = Setting.get_settings(), 
					cart = Cart,
					cabinet = Cabinet)

	def forgot_password():
		return flask.render_template("forgot_password.html",
					pages=InfoPage.query.all(),
					categories = Category.query.all(),
					settings = Setting.get_settings(), 
					cart = Cart,
					cabinet = Cabinet)




app.add_url_rule('/register', 'register', Cabinet.register, methods=["GET","POST"])
app.add_url_rule('/login', 'login', Cabinet.login, methods=["GET","POST"])
app.add_url_rule('/exit', 'exit', Cabinet.exit, methods=["GET","POST"])
app.add_url_rule('/my-account', 'my-account', Cabinet.my_account, methods=["GET","POST"])
app.add_url_rule('/edit-account', 'edit-account', Cabinet.edit_account, methods=["GET","POST"])
app.add_url_rule('/add_good_wishlist', 'add_good_wishlist', Cabinet.add_good_wishlist, methods=["POST"])
app.add_url_rule('/wishlist', 'wishlist', Cabinet.wishlist, methods=["GET","POST"])
app.add_url_rule('/remove_wishlist', 'remove_wishlist', Cabinet.remove_wishlist, methods=["GET","POST"])
app.add_url_rule('/add_good_compare', 'add_good_compare', Cabinet.add_good_compare, methods=["POST"])
app.add_url_rule('/compare', 'compare', Cabinet.compare, methods=["GET"])
app.add_url_rule('/change_password', 'change_password', Cabinet.change_password, methods=["GET","POST"])
app.add_url_rule('/edit_address', 'edit_address', Cabinet.edit_address, methods=["GET","POST"])
app.add_url_rule('/history', 'history', Cabinet.history, methods=["GET"])
app.add_url_rule('/downloads', 'downloads', Cabinet.downloads, methods=["GET"])
app.add_url_rule('/compare', 'compare', Cabinet.compare, methods=["GET"])
app.add_url_rule('/remove_good_compare', 'remove_good_compare', Cabinet.remove_good_compare, methods=["GET"])
app.add_url_rule('/forgot-password', 'forgot_password', Cabinet.forgot_password, methods=["GET","POST"])

#---------------------/cabinet/----------------------------------------

@app.route('/save_image', methods=["GET","POST"])
def save_image():
	if 'files[]' not in flask.request.files:
		resp = flask.jsonify({'message' : 'No file part in the request'})
		resp.status_code = 400
		return resp

	files = flask.request.files.getlist('files[]')

	errors = {}
	success = False
	filenames = []

	for file in files:
		if file and allowed_file(file.filename):
			filename = prefix_name(file_data=file)
			file.save(os.path.dirname(os.path.abspath(__file__)) + os.path.join(app.config['UPLOAD_FOLDER'], filename))
			with ProcessImage.open(os.path.dirname(os.path.abspath(__file__)) + os.path.join(app.config['UPLOAD_FOLDER'], filename)) as image:
				image.thumbnail((270, 270), ProcessImage.ANTIALIAS)
				image.save(os.path.dirname(os.path.abspath(__file__)) + os.path.join(config.THUMBNAIL_FOLDER, filename)) #and save it
			success = True
			filenames.append(filename)
			if flask.request.args.get('id') != 'null':
				good_id = flask.request.args.get('id')
			else:
				try:
					good_id = Good.query.order_by(Good.id.desc()).first().id + 1
				except:
					good_id = 1
			print(good_id)
			new_image = Image(good_id = int(good_id), file_name = filename)
			db.session.add(new_image)
			db.session.commit()

		else:
			errors[file.filename] = 'File type is not allowed'

	if success and errors:
		errors['message'] = 'File(s) successfully uploaded'
		errors['filenames'] = filenames
		resp = flask.jsonify(errors)
		resp.status_code = 206
		return resp
	if success:
		resp = flask.jsonify({'message' : 'Files successfully uploaded', 'filenames':filenames})
		resp.status_code = 201
		return resp
	else:
		resp = flask.jsonify(errors)
		resp.status_code = 400
		return resp

@app.route('/', methods=['GET', 'POST'])
def index_redirect():
	#print(flask.request.remote_addr)
	return flask.redirect('/home')

@app.route("/home", methods=['GET'])
def index():
	return flask.render_template("index.html",
		pages=InfoPage.query.all(),
		categories=Category.query.all(),
		settings = Setting.get_settings(),
		cart = Cart,
		sales = Sale.query.all(),
		macbooks = Category.query.filter_by(name='Macbook').first(),
		populars=Good.query.order_by(desc(Good.avg_rating)).limit(12).all(),
		top_goods=Top_good.query.all(),
		slider=Slider.query.all(),
		cabinet=Cabinet)

@app.route("/<cat_name>", methods=["GET"])
def catalog(cat_name):
	if 'view' not in flask.session:
		flask.session['view'] = 'grid'

	cat = Category.query.filter_by(name=cat_name).first()
	page = flask.request.args.get('page', type=int, default=1)
	if cat:

		order = flask.request.args.get('order', default='ASC')
		sort = flask.request.args.get('sort', default='pd.name')
		limit = flask.request.args.get('limit', type=int, default=12)

		if order == 'ASC' and sort == 'rating':
			data = Good.query.filter_by(cat_id = cat.id).order_by(asc(Good.avg_rating)).paginate(page, limit, False)
		elif order == 'DESC' and sort == 'rating':
			data = Good.query.filter_by(cat_id = cat.id).order_by(desc(Good.avg_rating)).paginate(page, limit, False)
		else:
			if order == 'ASC' and sort == 'pd.name':
				order_by = Good.name.asc()
			elif order == 'DESC' and sort == 'pd.name':
				order_by = Good.name.desc()
			elif order == 'ASC' and sort == 'p.price':
				order_by = Good.price.asc()
			elif order == 'DESC' and sort == 'p.price':
				order_by = Good.price.desc()
			elif order == 'ASC' and sort == 'p.model':
				order_by = Good.model.asc()
			elif order == 'DESC' and sort == 'p.model':
				order_by = Good.model.desc()
			else:
				order_by = Good.name.asc()

			data = Good.query.filter_by(cat_id = cat.id).order_by(order_by).paginate(page, limit, False)

		return flask.render_template("catalog.html",
			pages=InfoPage.query.all(),
			categories=Category.query.all(),
			settings = Setting.get_settings(),
			category=cat,
			data = data,
			cart = Cart,
			top_goods=Top_good.query.all(),
			cabinet=Cabinet)
	else:
		return flask.abort(404)

@app.route("/search", methods=["GET"])
def search():
	if 'view' not in flask.session:
		flask.session['view'] = 'grid'

	cat_id = flask.request.args.get('category_id', default='any')
	search_r = flask.request.args.get('search', default='')

	page = flask.request.args.get('page', type=int, default=1)
	order = flask.request.args.get('order', default='ASC')
	sort = flask.request.args.get('sort', default='pd.name')
	limit = flask.request.args.get('limit', type=int, default=12)

	if order == 'ASC' and sort == 'pd.name':
		order_by = Good.name.asc()
	elif order == 'DESC' and sort == 'pd.name':
		order_by = Good.name.desc()
	elif order == 'ASC' and sort == 'p.price':
		order_by = Good.price.asc()
	elif order == 'DESC' and sort == 'p.price':
		order_by = Good.price.desc()
	elif order == 'ASC' and sort == 'p.model':
		order_by = Good.model.asc()
	elif order == 'DESC' and sort == 'p.model':
		order_by = Good.model.desc()
	else:
		order_by = Good.name.asc()
	try:
		data = Good.query.filter(Good.name.like('%'+search_r+'%')).filter_by(cat_id = int(cat_id)).order_by(order_by).paginate(page, limit, False)
	except ValueError:
		data = Good.query.filter(Good.name.like('%'+search_r+'%')).order_by(order_by).paginate(page, limit, False)

	return flask.render_template("search.html",
			pages=InfoPage.query.all(),
			categories=Category.query.all(),
			settings = Setting.get_settings(),
			data=data,
			cart = Cart,
			cabinet=Cabinet)

@app.route("/quick_search", methods=['POST'])
def quick_search():
	req = flask.request.json
	goods = []
	try:
		db_req = Good.query.filter(Good.name.like('%'+req['search_r']+'%')).filter_by(cat_id = int(req['category_id'])).limit(5).all()
	except:
		db_req = Good.query.filter(Good.name.like('%'+req['search_r']+'%')).limit(5).all()
	for good in db_req:
		goods.append(good.as_dict())
	return json_dumps({'success': True, 'good':goods}), 200, {'ContentType':'application/json'}

@app.route("/sales", methods=["GET"])
def sales():
	if 'view' not in flask.session:
		flask.session['view'] = 'grid'

	page = flask.request.args.get('page', type=int, default=1)
	order = flask.request.args.get('order', default='ASC')
	sort = flask.request.args.get('sort', default='pd.name')
	limit = flask.request.args.get('limit', type=int, default=12)

	if order == 'ASC' and sort == 'pd.name':
		order_by = Good.name.asc()
	elif order == 'DESC' and sort == 'pd.name':
		order_by = Good.name.desc()
	elif order == 'ASC' and sort == 'p.price':
		order_by = Good.price.asc()
	elif order == 'DESC' and sort == 'p.price':
		order_by = Good.price.desc()
	elif order == 'ASC' and sort == 'p.model':
		order_by = Good.model.asc()
	elif order == 'DESC' and sort == 'p.model':
		order_by = Good.model.desc()
	else:
		order_by = Good.name.asc()

	data = Good.query.filter(Good.sales.any()).order_by(order_by).paginate(page, limit, False)

	return flask.render_template("sales.html",
			pages=InfoPage.query.all(),
			categories=Category.query.all(),
			settings = Setting.get_settings(),
			data=data,
			cart = Cart,
			cabinet=Cabinet)

@app.route('/change', methods=["GET"])
def change_view():
	new_view = flask.request.args.get('view')
	flask.session['view'] = new_view
	print(flask.request.args.get('back'), new_view)

	return flask.redirect(flask.request.args.get('back'))

@app.route("/catalog/<good_url>", methods=['GET'])
def good(good_url):
	good = Good.query.filter_by(url=good_url).first()
	return flask.render_template("good.html",
		pages=InfoPage.query.all(),
		categories=Category.query.all(),
		settings = Setting.get_settings(),
		good=good,
		cart = Cart,
		cabinet=Cabinet)

@app.route("/new_review", methods=["POST"])
def new_review():
	if captcha.validate():
		new_review = Review(user_name=flask.request.form['user_name'], 
			comment=flask.request.form['text'], 
			rate_id=flask.request.form['rating'], 
			good_id=flask.request.args.get('good_id'),
			is_published=False)
		db.session.add(new_review)
		db.session.commit()

		return flask.redirect('/catalog/'+ flask.request.args.get('backurl'))
	else:
		flask.flash('Неверный код. Попробуйте снова')
		flask.redirect('/catalog/'+ flask.request.args.get('backurl'))

@app.route('/pages/<page_id>')
def pages(page_id):
	return flask.render_template('page.html',
		categories=Category.query.all(),
		pages=InfoPage.query.all(),
		settings = Setting.get_settings(),
		page=InfoPage.query.get(page_id),
		cart = Cart)

@app.route('/contact-us', methods=['GET', 'POST'])
def contact_us():
	if flask.request.method == 'POST':
		if captcha.validate():
			if flask.request.form['name'] == '' or flask.request.form['email'] == '' or flask.request.form['enquiry'] == '':
				flask.flash('Не все поля заполнены. Попробуйте снова')
				flask.redirect(flask.url_for('contact_us'))
			else:
				new_message = Contact_us(name=flask.request.form['name'], 
					email=flask.request.form['email'], 
					text=flask.request.form['enquiry'])
				db.session.add(new_message)
				db.session.commit()
				flask.flash('Спасибо! Ваше сообщение принято')
				flask.redirect(flask.url_for('contact_us'))
		else:
			flask.flash('Код введен неверно. Попробуйте снова')
			flask.redirect(flask.url_for('contact_us'))

	return flask.render_template('contact_us.html',
		categories=Category.query.all(),
		pages=InfoPage.query.all(),
		settings = Setting.get_settings(),
		cart = Cart)

if __name__ == "__main__":
	app.run(host=config.host, port=config.port)#, ssl_context='adhoc')
