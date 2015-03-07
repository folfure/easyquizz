# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.escape import url_escape
import py.tools as tools
import py.json_handler
import os



TITLE ='Génies en Herbe'




class Team(object):
    def __init__(self,name):
        self.name = name
        self.players = set()
        self.score = 0

    def add_player(self):
        self.players.add(player)

class Player(object):
    counter=1
    def __init__(self, name, team = None):
        self.name = name
        self.id = Player.counter
        Player.counter+=1
        self.socket = None
        self.team = team

class Game(object):
    def __init__(self):
        self.teams = [Team('Loosers'), Team('Best Ones')]
        self.clients = set()
        self.players = []

    def find_player(self, name):
        for p in self.players:
            if p.name == name:
                return p

    def get_player(self, name):
        p = self.find_player(name)
        if p is None:
            p = Player(name)
        
        return p

    def publish(self,msg):
        print "publishing"
        for client in self.clients:
            print "--client",client.player
            client.write_message(msg)


IOLOOP = tornado.ioloop.IOLoop.instance()
GAME = Game()
SECTIONS = tools.create_sections("questions")



class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")


class MainHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self):
        if not self.current_user:
            self.redirect("/login")
            return

        name = tornado.escape.xhtml_escape(self.current_user)
        p = GAME.get_player(name)
        if p.team:
            team_name = p.team.name
        else:
            team_name=""
        self.render("static/player.html", title=TITLE, team_name=team_name, user_name=p.name)


class LoginHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self):
        self.render('static/login.html',title=TITLE)

    @tornado.web.asynchronous
    def post(self):
        self.set_secure_cookie("user", self.get_argument("name"))
        self.redirect("/")
        IOLOOP.add_callback(lambda :self.add_player(self.get_argument("name")))


















class GameHandler(py.json_handler.JsonHandler):
    @tornado.web.asynchronous
    def get(self):
        req_type = self.request.arguments['req_type'][0]
        print req_type
        if req_type == 'register_user':
            user_name = self.request.arguments['user_name'][0]
            IOLOOP.add_callback(lambda :self.add_player())

    def add_player(self, name, team):
        self.response['id'] = GAME.add_player(name, team)
        self.write_json()
        print "json written"
        IOLOOP.add_callback(lambda:GAME.publish('%s joined the team %s'%(name,team)))


class HTMLAdminHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):
        self.render('static/admin.html', title=TITLE)


class HTMLQuizzHandler(tornado.web.RequestHandler):
    
    @tornado.web.asynchronous
    def get(self):
        section_id = self.get_argument('section',default=0)
        question_id = self.get_argument('question',default=0)
        section_id = int(section_id)
        question_id = int(question_id)

        section_id = max(0, min(int(section_id), len(SECTIONS)-1))
        section = SECTIONS[section_id]

        if question_id == -1:
          question_id = len(section.questions)-1

        question_id = max(0, min(question_id, len(section.questions)-1))
        question = section.questions[question_id]

        with open("static/template.html") as f:
            self.write(f.read()%dict(  
                  max_question=len(section.questions)-1, 
                  max_section=len(SECTIONS)-1,
                  section_id=section_id,
                  question_id=question_id,
                  questions=",".join(["'%s'"%i for i in section.get_contents()]),
                  question_html=question.html(),
                  section_title = section.name.upper(),
                  question_id_disp=question_id+1

                  ) )
        self.finish()



class WebSocketBuzzHandler(tornado.websocket.WebSocketHandler):
  def __init__(self,*args,**kwargs):
    tornado.websocket.WebSocketHandler.__init__(self, *args,**kwargs)
    self.player = None
  def clean(self):
    GAME.clients.remove(self)
    if self.player:
        self.player.socket = None



  def open(self, *args, **kwargs):
    print("open", "WebSocketChatHandler")
    self.player = GAME.get_player(url_escape(self.get_argument('user')))
    self.player.socket = self
    IOLOOP.add_callback(lambda s=self:GAME.clients.add(s))
    IOLOOP.add_callback(lambda:GAME.publish('client connected'))


  def on_message(self, message):        
    IOLOOP.add_callback(lambda:GAME.publish(message))

        
  def on_close(self):

    IOLOOP.add_callback((lambda :self.clean() and GAME.publish('client disconnected')))
    


app = tornado.web.Application([
                                (r'/', MainHandler), 
                                (r'/buzz', WebSocketBuzzHandler), 
                                (r'/login', LoginHandler), 
                                (r'/quizz',  HTMLQuizzHandler ),
                                (r'/admin',  HTMLAdminHandler ),
                                (r'/game',  GameHandler ),
                                (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "static"}),
                                (r"/questions/(.*)", tornado.web.StaticFileHandler, {"path": "questions"}),
                                ],
                                debug=True,
                                cookie_secret="WOUHOUWCEQUIZZESTEXAGE"
        )

app.listen(80)
IOLOOP.start()



