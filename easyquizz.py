# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.escape import url_escape
from tornado.web import MissingArgumentError
import py.tools as tools
import py.json_handler
import os
import json
from pprint import pprint
import sqlite3




TITLE ='Loose yourself to Buzz'

class Team(object):
    def __init__(self,name):
        self.name = name
        self.players = set()
        self.score = 0

    def add_player(self,player):
        self.players.add(player)
        player.team = self

class Player(object):
    counter=1
    def __init__(self, name, team = None):
        self.name = name
        self.id = Player.counter
        Player.counter+=1
        self.socket = None
        self.team = team

class Game(object):
    def __init__(self, db_name):
        new_db = not os.path.exists(db_name)
        self.db_conn = sqlite3.connect(db_name,detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self.cursor = self.db_conn.cursor()
        self.sockets = dict()
        self.players = dict()
        self.teams = dict()
        self.admin = None
        self.current_section = 0
        self.current_question = 0
        self.sections = tools.create_sections("questions")
        print self.sections
        self.add_team("unassigned")

        if new_db:
            print "creating db"
            with self.db_conn:
                self.cursor.execute("CREATE TABLE player(name varchar unique, team varchar)")  
                self.cursor.execute("CREATE TABLE answer(player varchar, section_id integer, question_id integer, response_time real)")          
        else:
            #read db and fill players
            with self.db_conn:
                for name, team in self.cursor.execute('SELECT name, team FROM player order by name'):
                    print name, team
                    team_obj = Team(team)
                    self.players[name] = player = Player(name)
                    self.add_team(team).add_player(player)
                    


    def add_team(self,team_name):
        return self.teams.setdefault(team_name,Team(team_name))

    def add_player(self, name, team_name="unassigned"):
        if self.get_player(name) is None:
            with self.db_conn:
                try:
                    self.cursor.execute("INSERT INTO player(name, team) values (?,?)", (name, team_name))
                    self.players[name] = player = Player(name)
                    self.add_team(team_name).add_player(player)
                    self.publish_admin(type='info', msg='db insert : %s'%name)
                except sqlite3.IntegrityError:
                    print "player already exists !!!!"
        self.publish_admin(type='info', msg='login : %s'%name)
        return 0

    def get_player(self, name):
        if name in self.players:
            return self.players[name]
        else:
            return None

    def set_admin(self):
        if self.admin:
            return 1
        else:
            self.admin = True
            return 0

    def set_admin_socket(self,socket):
        if self.admin is None:
            self.admin = socket


    def set_socket(self, socket, name):

        self.sockets[name] = socket
        socket.player = name
        self.players[name].socket = socket

    def publish_players(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        for pname, socket in self.sockets.iteritems():
            socket.write_message(msg)

    def publish_admin(self,type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        if self.admin and self.admin != True:
            self.admin.write_message(msg)

    def publish_all(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        if self.admin and self.admin != True:
            self.admin.write_message(msg)
        for pname, socket in self.sockets.iteritems():
            socket.write_message(msg)


    def publish(self,msg):
        print "publishing", msg
        for p in self.players:
            print "--client",p.name, p.client
            print msg
            p.client.write_message(msg)

    def socket_disconnected(self, socket):
        pname = socket.player
        self.sockets.pop(pname)
        self.publish_players(type='log',msg="User %s socket disconnected"%pname)
        self.publish_admin(type='player_disconnected',name=pname)

    def socket_admin_disconnected(self):
        self.admin=None

    def update_teams_composition(self, composition):
        with self.db_conn:
            for d in composition:
                team_name = str(d['team'])
                self.add_team(team_name).players = set([GAME.players[p] for p in d['players']])
                for player_name in d['players']:
                    player = self.players[player_name]
                    if player.team.name != team_name:
                        player.team = self.teams[team_name]
                        self.cursor.execute("UPDATE player set team='%s' where name='%s'"%(team_name,player_name))
                    if player.socket:
                        player.socket.send_msg(type='team_changed',team=team_name)
                        GAME.publish_admin(type='info', msg="%s changed to team %s "%(player_name, team_name))
                    else:
                        GAME.publish_admin(type='info', msg="%s NEED RELOAD PAGE SINCE HIS TEAM CHANGED"%player_name)



    def __del__(self):
        self.db_conn.close()



IOLOOP = tornado.ioloop.IOLoop.instance()

GAME = Game(db_name="easyquizz.db")



class BaseHandler(tornado.web.RequestHandler):
    
    def get_current_user(self):
        return self.get_secure_cookie("user")
    
    @property
    def current_admin(self):
        return self.get_secure_cookie("admin")

    @current_admin.setter
    def current_admin(self, value):
        self.set_secure_cookie("admin",value)

    def logoff_user(self):
        if self.current_user:
            self.clear_cookie("user")

    def logoff_admin(self):
        if self.current_admin:
            self.clear_cookie("admin")



class LoginHandler(BaseHandler):
    def get(self,*args,**kwargs):
        params = self.request.arguments
        if params.has_key('logoff') :
            if '/admin' in args:
                self.logoff_admin()
                self.redirect('/login/admin')
            else:
                self.logoff_user()
                self.redirect('/login')
            return

        if '/admin' in args :
            print kwargs
            if self.current_admin :
                self.redirect('/admin')
            else:
                self.render('static/login.html',title=TITLE, 
                            post_url='/login/admin', password_display='block', name_display='none')

        elif self.current_user:
            self.redirect('/')

        else:
            self.render('static/login.html',title=TITLE, 
                            post_url='/login', password_display='none', name_display='block')

    def post(self,*args,**kwargs):
        if '/admin' in args:
            error = GAME.set_admin()
            if error:
                self.redirect('/login/admin/')
                return
            self.current_admin = '1'
            self.redirect('/admin')
        else:
            name=self.get_argument("name")
            self.set_secure_cookie("user", name)
            try:
                GAME.add_player(name)
                self.redirect('/')
            except Exception as e:
                print e, e.__class__
                print "couldn't add player %s"%(name)
                self.redirect('/login')


class GameHandler(tornado.web.RequestHandler):

    def post(self,*args,**kwargs):
        if '/add_team' in args: 
            team_name = self.get_argument("team_name")
            GAME.add_team(team_name)
            print "new_team",team_name
            self.redirect('/admin')



class PlayerHandler(BaseHandler):
    def get(self,*args,**kwargs):
        print self.request.uri
        if not self.current_user:
            self.redir
            return

        name = tornado.escape.xhtml_escape(self.current_user)
        p = GAME.get_player(name) 
        if p:    
            self.render("static/player.html", title=TITLE, team_name=p.team, user_name=p.name)
        else:
            self.clear_cookie("user")
            self.redirect('/login')

class AdminHandler(BaseHandler):
    def get(self,*args,**kwargs):
        print self.request.uri
        if not self.current_admin:
            self.redirect("/login/admin")
            return
        else:
            GAME.set_admin()
            self.render('static/admin.html', 
                    title=TITLE, 
                    teams=sorted(GAME.teams.values(),key=lambda team:team.score),
                    sections=GAME.sections)
            return


class HTMLQuizzHandler(tornado.web.RequestHandler):

    def get(self):
        section_id = self.get_argument('section',default=0)
        question_id = self.get_argument('question',default=0)
        section_id = int(section_id)
        question_id = int(question_id)

        section_id = max(0, min(int(section_id), len(GAME.sections)-1))
        section = GAME.sections[section_id]

        if question_id == -1:
          question_id = len(section.questions)-1

        question_id = max(0, min(question_id, len(section.questions)-1))
        question = section.questions[question_id]

        with open("static/template.html") as f:
            self.write(f.read()%dict(  
                  max_question=len(section.questions)-1, 
                  max_section=len(GAME.sections)-1,
                  section_id=section_id,
                  question_id=question_id,
                  questions=",".join(["'%s'"%i for i in section.get_contents()]),
                  question_html=question.html(),
                  section_title = section.name.upper(),
                  question_id_disp=question_id+1
                  ) )
        self.finish()

class WebSocketAdminHandler(tornado.websocket.WebSocketHandler):
    def __init__(self,*args,**kwargs):
        tornado.websocket.WebSocketHandler.__init__(self, *args,**kwargs)
        self.admin = None

    def open(self, *args, **kwargs):
        print("open", "WebSocketAdminHandler")
        GAME.set_admin_socket(self)
    
    def on_message(self, message):
        msg = json.loads(message)
        typ = msg['type']
        if typ=='correct':
            GAME.publish_admin(type='info', msg='%s correct answer %.5f'%(self.player,msg['when']))
        elif typ=='teams_compo':
            GAME.update_teams_composition(msg['compo'])
            GAME.publish_admin(type='info', msg="Teams changed")

    def on_close(self):
        GAME.socket_admin_disconnected()

    def send_msg(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        self.write_message(msg)

class WebSocketBuzzHandler(tornado.websocket.WebSocketHandler):
    def __init__(self,*args,**kwargs):
        tornado.websocket.WebSocketHandler.__init__(self, *args,**kwargs)
        self.player = None

    def open(self, *args, **kwargs):
        print("open", "WebSocketPlayerHandler")
        GAME.set_socket(self, self.get_argument('user'))
    
    def on_message(self, message):
        msg = json.loads(message)
        if msg['type']=='buzz':
            GAME.publish_all(type='info', msg='%s buzzed %.5f'%(self.player,msg['when']))

        
    def on_close(self):
        GAME.socket_disconnected(self)

    def send_msg(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        self.write_message(msg)
    


app = tornado.web.Application([
                                (r'/', PlayerHandler), 
                                (r'/buzz', WebSocketBuzzHandler), 
                                (r'/adminws', WebSocketAdminHandler), 
                                (r'/login(.*)', LoginHandler), 
                                (r'/quizz',  HTMLQuizzHandler ),
                                (r'/admin',  AdminHandler ),
                                (r'/game(.*)',  GameHandler ),
                                (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "static"}),
                                (r"/questions/(.*)", tornado.web.StaticFileHandler, {"path": "questions"}),
                                ],
                                debug=True,
                                cookie_secret="WOUHOUWCEQUIZZESTEXAGE"
        )

app.listen(80)
IOLOOP.start()



