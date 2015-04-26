# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.template
from tornado.escape import url_escape
from tornado.web import MissingArgumentError
import py.tools as tools
import py.json_handler
import os
import json
from pprint import pprint
import sqlite3

TITLE ='Loose yourself to Buzz'
TEMPLATES = tornado.template.Loader("static/template")
class Game(object):
    def __init__(self, db_name):
        new_db = not os.path.exists(db_name)
        #sqlite3 database
        self.db_conn = sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        #cursor for making queries to sql db
        self.cursor = self.db_conn.cursor()
        # map of player name to websocket
        self.sockets = dict()
        # map of player name to team name
        self.players = dict()
        # map of team names to player set
        self.teams = dict()
        # websocket to screen display
        self.screens = []
        # map of team name to tuple (score, team name)
        self.team_scores = dict()
        # map of player name to tuple (score, player name)
        self.player_scores = dict()
        #admin web socket
        self.admin = None
        self.quizz_screen = tools.QuizzPlayer("questions")

        pprint(self.quizz_screen.sections)

        self.add_team("unassigned")

        if new_db:
            print "creating db"
            with self.db_conn:
                self.cursor.execute("CREATE TABLE player(name varchar unique, team varchar)")  
                self.cursor.execute("CREATE TABLE answer(player varchar, section_id integer, question_id integer, response_time real)")          
        else:
            #read db and fill players
            with self.db_conn:
                for player, team in self.cursor.execute('SELECT name, team FROM player order by name'):
                    self.add_player(player,team)
        self.reset_buzzers()
                 
    #to do
    def reset_buzzers(self, exclude=None):
        self.current_player = None
        self.current_team = None
        self.cant_answer = set()
        if exclude:
            self.cant_answer.add(exclude)
        for player, socket in self.sockets.iteritems():
            if exclude and self.players[player]==exclude:
               continue
            socket.write_message(dict(type='enable_buzzer'))

    #to do
    def je_dis_non(self):
        if not self.current_team:
            self.publish_admin(type='info',msg="warning : no active team")
        else:
            #stop current timer for everyone
            pass

    #to do
    def handle_buzz(self, player, team):
        if team in self.cant_answer:
            return
        if self.current_player and self.current_team:
            return 
        else:
            pass

    def add_team(self,team):
        self.team_scores.setdefault(team,[0, team])
        return self.teams.setdefault(team,set())
    
    def add_player(self,player,team="unassigned"):
        self.add_team(team).add(player)
        self.players[player] = team
        self.player_scores.setdefault(player,[0, player])

    def create_player(self, player, team="unassigned"):
        if not self.players.has_key(player):
            with self.db_conn:
                try:
                    self.cursor.execute("INSERT INTO player(name, team) values (?,?)", (player, team))
                    self.add_player(player, team)
                    self.publish_admin(type='info', msg='db insert : %s'%player)
                except sqlite3.IntegrityError:
                    print "player already exists !!!!"
        self.publish_admin(type='info', msg='login : %s'%player)
        return 0


    def add_screen(self, screen):
        self.screens.append(screen)

    def remove_screen(self, screen):
        self.screens.remove(screen)

    def set_admin(self):
        if self.admin:
            return 1
        else:
            self.admin = True
            return 0

    def set_admin_socket(self,socket):
        #what if self.admin is True ?
        if self.admin is None:
            self.admin = socket

    def set_socket(self, socket, name):
        self.sockets[name] = socket
        socket.player = name

    def publish_player(self, player, type, **kwargs):
        if player in self.sockets:
            msg = dict(type=type)
            msg.update(kwargs)
            self.sockets[player].write_message(msg)
            return 0
        return 1

    def get_player_data(self,player):
        return dict(player=player, team=self.players[player], 
                    team_scores=sorted(self.team_scores.values()), 
                    player_scores=sorted(self.player_scores))

    def publish_players(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        for socket in self.sockets.values():
            print socket,msg
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
        for socket in self.sockets.values():
            socket.write_message(msg)

    def publish_screen(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        for screen in self.screens:
            screen.write_message(msg)

    def socket_disconnected(self, player):
        self.sockets.pop(player)
        self.publish_players(type='log',msg="User %s socket disconnected"%player)
        self.publish_admin(type='player_disconnected',name=player)

    def socket_admin_disconnected(self):
        self.admin=None

    def update_teams_composition(self, composition):
        scores = sorted(self.team_scores.values())
        with self.db_conn:
            for new_team, new_players in composition.iteritems():
                #update information of new players only (if moved then he would be )
                self.add_team(new_team)
                for new_p in set(new_players).difference(self.teams[new_team]) :
                    self.players[new_p] = new_team
                    self.cursor.execute("UPDATE player set team='%s' where name='%s'"%(new_team, new_p))
                    self.publish_admin(type='info', msg="%s changed team to %s"%(new_p,new_team))
                    print new_p, new_team
                    if self.publish_player(new_p, type='update_html', data={'scores':TEMPLATES.load("scores.html").generate(scores=scores, team=new_team)}):
                        self.publish_admin(type='info', msg="%s NEED RELOAD PAGE SINCE HIS TEAM CHANGED"%new_p)

                self.teams[new_team] = new_players

    def go_to_question(self, section_id, question_id):
        #to do deactivate buzzers ?
        self.publish_screen(type="update_html", data={'slide':self.quizz_screen.go_to_question(section_id, question_id)})
        self.publish_admin(type='update_html', data={'sections':TEMPLATES.load("sections.html").generate(sections=self.quizz_screen.sections, section_id=section_id, question_id=question_id)})



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
                GAME.socket_admin_disconnected()                
                self.redirect('/admin')
            else:
                self.write(TEMPLATES.load("login.html").generate(title=TITLE, 
                            post_url='/login/admin', password_display='block', name_display='none'))
                self.finish()

        elif self.current_user:
            self.create_player(self.current_user)
            self.redirect('/')

        else:
            self.write(TEMPLATES.load("login.html").generate(title=TITLE, 
                            post_url='/login', password_display='none', name_display='block'))
            self.finish()

    def post(self,*args,**kwargs):
        #to do secure
        if '/admin' in args:
            error = GAME.set_admin()
            if error:
                #to do add error div in all pages
                self.redirect('/login/admin?errid=5')
                return
            self.current_admin = '1'
            self.redirect('/admin')
        else:
            player=self.get_argument("name")
            self.set_secure_cookie("user", player)
            try:
                GAME.create_player(player)
                self.redirect('/')
            except Exception as e:
                print e, e.__class__
                print "couldn't add player %s"%(player)
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

        if not self.current_user:
            self.redirect('/login')
            return

        player = tornado.escape.xhtml_escape(self.current_user)
        if GAME.players.has_key(player):    
            if self.request.uri == '/pdata':
                output = json.dumps(GAME.get_player_data(player))
                self.write(output)
                self.finish()
            else:
                self.write(TEMPLATES.load("player.html").generate(
                                title=TITLE, 
                                scores=sorted(GAME.team_scores.values()), 
                                team=GAME.players[player],
                                player=player ))
                self.finish()
        else:
            # shouldn't happen (user with cookie but not registered in the game...)
            self.clear_cookie("user")
            self.redirect('/login')

class AdminHandler(BaseHandler):
    def get(self,*args,**kwargs):
        print "AdminHandler.get : GAME admin", GAME.admin
        if not self.current_admin:
            self.redirect("/login/admin")
            return
        else:
            GAME.socket_admin_disconnected()
            self.write(TEMPLATES.load("admin.html").generate(
                    title=TITLE, 
                    scores=sorted(GAME.team_scores.values()),
                    teams=sorted(GAME.teams.items()),
                    sections=GAME.quizz_screen.sections,
                    section_id=GAME.quizz_screen.section_id, 
                    question_id=GAME.quizz_screen.question_id))
            self.finish()
            return

class WebSocketScreenHandler(tornado.websocket.WebSocketHandler):
    def __init__(self,*args,**kwargs):
        tornado.websocket.WebSocketHandler.__init__(self, *args,**kwargs)

    def open(self, *args, **kwargs):
        print("open", "WebSocketScreenHandler")
        GAME.add_screen(self)
        self.set_nodelay(True)
    
    def on_close(self):
        GAME.remove_screen(self)

    def send_msg(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        self.write_message(msg)


class HTMLQuizzHandler(tornado.web.RequestHandler):

    def get(self):
        self.write(TEMPLATES.load("screen.html").generate(
                    title=TITLE,
                    scores=sorted(GAME.team_scores.values()),
                    slide=GAME.quizz_screen.get_current_content()
                    ))
        self.finish()

class WebSocketAdminHandler(tornado.websocket.WebSocketHandler):
    def __init__(self,*args,**kwargs):
        tornado.websocket.WebSocketHandler.__init__(self, *args,**kwargs)
        self.admin = None

    def open(self, *args, **kwargs):
        print("open", "WebSocketAdminHandler")
        #to do check no admin already logged
        #if GAME.admin is set to True it means admin cam efrom post (admin form)
        #if GAME.admin is None amdin came from coookie without 
        if GAME.admin not in (None, True):
            self.close(code=5, reason="An admin is already logged")
        else:
            GAME.set_admin_socket(self)
            self.set_nodelay(True)
    
    def on_message(self, message):
        msg = json.loads(message)
        typ = msg['type']
        if typ=='correct':
            GAME.publish_admin(type='info', msg='%s correct answer %.5f'%(self.player,msg['when']))
        elif typ=='teams_compo':
            GAME.update_teams_composition(msg['compo'])
            GAME.publish_admin(type='info', msg="Teams changed")
        elif typ=="go_to_question":
            print "go_to_question",msg
            GAME.go_to_question(section_id=msg['sec_id'], question_id=msg['q_id'])

    def on_close(self):
        print "WebSocketAdminHandler.on_close : GAME admin", GAME.admin
        GAME.socket_admin_disconnected()
        print "no more admin ? ",GAME.admin

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
        self.set_nodelay(True)
    
    def on_message(self, message):
        msg = json.loads(message)
        if msg['type']=='buzz':
            GAME.publish_all(type='info', msg='%s buzzed %.5f'%(self.player,msg['when']))

        
    def on_close(self):
        GAME.socket_disconnected(self.player)

    def send_msg(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        self.write_message(msg)
    


app = tornado.web.Application([
                                (r'/', PlayerHandler), 
                                (r'/pdata', PlayerHandler), 
                                (r'/buzz', WebSocketBuzzHandler), 
                                (r'/adminws', WebSocketAdminHandler), 
                                (r'/screenws', WebSocketScreenHandler), 
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



