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
import time
import thread

TITLE ='Loose yourself to Buzz'
TEMPLATES = tornado.template.Loader("static/template")
class Game(object):
    
    TIMER_DURATION = 5          # time to answer a question in seconds
    
    def __init__(self, db_name):
        new_db = not os.path.exists(db_name)
        self.db_conn = sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self.cursor = self.db_conn.cursor()
        self.sockets = dict()           # {playerName: socketObject}. Dict in which key is the player name and the value is the socket object for this player. 
        self.players = dict()           # {playerName: teamName}. Dict in which key is player name. Values is player team.
        self.teams = dict()             # {teamName: set([players])}. Dict in which key is player name. Values is player team.
        self.team_scores = dict()       # {teamName: [score, teamName]}.Dict in which key is team name. Values is a list where first item is the score, second item is the team name again.
        self.player_scores = dict()     # {playerName: [score, playerName]}.Dict in which key is player name. Values is a list where first item is the score, second item is the player name again.
        self.admin = None
        self.current_section = 0
        self.current_question = 0
        self.current_question_score = 5
        self.sections = tools.create_sections("questions")
        self.referenceTimeStamp = self.getCurrentTimestamp() # Timestamp UTC. 
        self.gameOpen = 10                      # contains 0 when game is closed. COntains a timestamp when game is open. Timestamp correspond to the time when the game was open. 
        self.can_answer = self.teams.keys()     # ALl the teams can answer at the beginning.
        print "Reference Timestamp: "+str(self.referenceTimeStamp)

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
    
    # Returns the current UTC timestamp. 
    #Maybe not accurate enough. Some systems gives timestamp with a second accuracy, not below.
    def getCurrentTimestamp(self):
        return int(round(time.time()*1000)) + time.timezone
    
    
    
    #Reactivate buzzers for the authorized teams.
    def reset_buzzers(self):
        self.publish_admin(type='info',msg="Resetting buzzers for authorized teams.")
        for team in self.can_answer:
            self.publish_team(team, type='buzzerActive', on=0)
        self.publish_admin(type='info',msg="Done.")
            
        

    # Triggered by game master at the end of the timer, when team that buzzed gives the wrong answer.
    # Team is excluded from the game for the current question.
    def je_dis_non(self):
        if not self.current_team or not self.current_player:
            self.publish_admin(type='info',msg="warning : no active team or player")
        else:
            # Store team in can't answer team list.
            self.exclude(self.current_team)
            # Reactivate buzzers for the other to continue the same question.
            self.reset_buzzers()
    
    # Triggered by game master at the end of the timer, when team that buzzed gives the wrong answer.
    # Team score is increase by current question score and game is closed.
    def je_dis_oui(self):
        if not self.current_team or not self.current_player:
            self.publish_admin(type='info',msg="warning : no active team or player")
        else:
            # Increase current team score by question score.
            updateScore(self.current_team, self.current_question_score)
            # Increase current player score?
            
            # Reactivate buzzers for the other to continue the question.
            self.closeGame()


    
    
    # Exclude team from the current question.
    def exclude(team):
        self.can_answer.remove(team)
        self.cant_answer.append(team)
        
            
    # returns True if Game is open and players can buzz.
    def isGameOpen(self):
        if self.gameOpen > 0:
            return True
        else:
            return False
    
    def openGame(self):
        self.gameOpen = self.getCurrentTimestamp()
        self.current_team = None
        self.current_player = None
        self.reset_buzzers()
        
    def closeGame(self):
        self.gameOpen = 0
    
    #to do
    def handle_buzz(self, player, timeBuzz):
        # self.reset_buzzers()
        playerTeam = self.players[player]
        if playerTeam in self.can_answer and self.isGameOpen() and self.current_team != "":
            # Player takes hand.
            # Block others buzzers
            self.publish_all(GAME.publish_players(type='buzzerActive', on=0))
            self.publish_all(GAME.publish_all(type='info', msg='All buzzers are blocked'))
             
            self.current_team = playerTeam
            self.current_player = player
            self.publish_all(GAME.publish_all(type='info', msg='Team %s has hand for 5 seconds'%playerTeam))
            
            # start timer
            try:
                thread.start_new_thread( self.simpleTimer, (GAME.TIMER_DURATION, ) )
            except:
                print "Error: unable to start timer -> continue without timer."
            
    
    # Countdown from duration (in seconds) to zero.
    def simpleTimer(self, duration):
        cpt = duration
        while cpt >= 1:
            self.publish_all(GAME.publish_all(type='info', msg=str(cpt)+'...'))
            time.sleep(1)
            cpt = cpt - 1
        #self.passHand()
        
    # Launched at the end of the timer. Reactivate all buzzers.
    def passHand(self):
        self.current_team = ""
        self.current_player = ""
        # Reactivate buzzers.
        self.publish_all(GAME.publish_players(type='buzzerActive', on=1))
        self.publish_all(GAME.publish_all(type='info', msg='End of Hand, buzzers are reactivated!'))
    
    
    def add_team(self,team):
        # if new team is not unassigned, remove unassigned if it still exists. Otherwise, unsassigned appears as ghost in the scores (1. team 1, 2. team 2, 4. team 3) 
        if team != "unassigned" and "unassigned" in self.teams.keys():
            self.team_scores.pop("unassigned")
            self.teams.pop("unassigned")
        self.team_scores.setdefault(team,[0, team])
        return self.teams.setdefault(team,set())
    
    
   # Returns score of team.
    def getTeamScore(self, team):
        if self.teamExist(team):
            return int(self.team_scores[team][0])
        else:
            raise Exception("Team %s does not exist!"%team)
        
        
    # returns True if team exist, false otherwise.
    def teamExist(self, team):
        if team in self.teams.keys():
            return True
        else:
            return False
    
    def getScores(self):
        return sorted(self.team_scores.values(),reverse=True)
    
    # Sets team score to new_score.
    # Tested. OK.
    def setTeamScore(self, team, new_score):
        # if team exists.
        if self.teamExist(team):
            # Negative scores not allowed.
            if int(new_score) < 0:
                new_score = 0
            self.team_scores[team][0] = new_score
            self.publish_all(type='info', msg="New Score for team %s: %d"%(team,new_score))
            self.notifyScores()
            return new_score
        return False
    
    # Update score by increment. Uses setTeamScore.
    # Tested. OK.
    def updateScore(self, team, score_inc):
        if team in self.team_scores.keys():
            new_score = self.getTeamScore(team) + int(score_inc)
            self.setTeamScore(team, new_score) 
    
    # Notifies all players and admin with scores.
    def notifyScores(self):
        scores = self.getScores()
        # Loop over players
        for player in self.sockets:
            team = self.players[player]
            self.publish_player(player, type='update_html', data={'scores':TEMPLATES.load("scores.html").generate(scores=scores, team=team)})
        self.publish_admin(type='update_html', data={'scores':TEMPLATES.load("scores_admin.html").generate(scores=scores, team="")})
        
    def add_player(self,player,team="unassigned"):
        if not self.teamExist("unassigned"):
            team = self.teams.keys()[0]
            
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
    
    # Sets socket for player.
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

    # Publish to all players of a team.
    def publish_team(self, team, type, **kwargs):
        for player in self.teams[team]:
            self.publish_player(player, type, **kwargs)
        
    def get_player_data(self,player):
        return dict(player=player, team=self.players[player], 
                    team_scores=self.getScores(), 
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

    def socket_disconnected(self, player):
        self.sockets.pop(player)
        self.publish_players(type='log',msg="User %s socket disconnected"%player)
        self.publish_admin(type='player_disconnected',name=player)

    def socket_admin_disconnected(self):
        self.admin=None

    def update_teams_composition(self, composition):
        scores = self.getScores()
        with self.db_conn:
            for new_team, new_players in composition.iteritems():
                #update information of new players only (if moved then he would be )
                self.add_team(new_team)
                for new_p in set(new_players).difference(self.teams[new_team]) :
                    self.players[new_p] = new_team
                    self.cursor.execute("UPDATE player set team='%s' where name='%s'"%(new_team, new_p))
                    GAME.publish_admin(type='info', msg="%s changed team to %s"%(new_p,new_team))
                    print new_p, new_team
                    if GAME.publish_player(new_p, type='update_html', data={'scores':TEMPLATES.load("scores.html").generate(scores=scores, team=new_team)}):
                        GAME.publish_admin(type='info', msg="%s NEED RELOAD PAGE SINCE HIS TEAM CHANGED"%new_p)

                self.teams[new_team] = new_players
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
        print "LoginHandler"
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
        print "GameHandler"
        if '/add_team' in args: 
            team_name = self.get_argument("team_name")
            GAME.add_team(team_name)
            print "new_team",team_name
            self.redirect('/admin')


# Called when players connects to ipaddress. Either he never connects and he is redirected to /login.
# or he already connected and he is redirected to his buzz page. 
class PlayerHandler(BaseHandler):
    def get(self,*args,**kwargs):
        print "PlayerHandler"
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
                                scores=GAME.getScores(), 
                                team=GAME.players[player],
                                player=player ))
                self.finish()
        else:
            # shouldn't happen (user with cookie but not registered in the game...)
            self.clear_cookie("user")
            self.redirect('/login')

# Called when someone connects to ipaddress/admin
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
                    scores=GAME.getScores(),
                    teams=GAME.teams.items(),
                    sections=GAME.sections))
            self.finish()
            return


class HTMLQuizzHandler(tornado.web.RequestHandler):

    def get(self):
        print "HTMLQuizzHandler"
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

# Websocket to admin.
class WebSocketAdminHandler(tornado.websocket.WebSocketHandler):
    def __init__(self,*args,**kwargs):
        tornado.websocket.WebSocketHandler.__init__(self, *args,**kwargs)
        self.admin = None
        

    def open(self, *args, **kwargs):
        print("open", "WebSocketAdminHandler")
        #to do check no admin already logged
        #if GAME.admin is set to True it means admin cam efrom post (admin form)
        #if GAME.admin is None amdin came from coookie without 
        # if GAME.admin is not (None, True):
            # self.close(code=5, reason="An admin is already logged")
        # else:
        GAME.set_admin_socket(self)
        self.set_nodelay(True)
        GAME.publish_admin(type='info', msg='Reference Timestamp : %d'%GAME.referenceTimeStamp)
    
    def on_message(self, message):
        msg = json.loads(message)
        print msg
        typ = msg['type']
        if typ=='correct':
            GAME.publish_admin(type='info', msg='%s correct answer %.5f'%(self.player,msg['when']))
        elif typ=='teams_compo':
            GAME.update_teams_composition(msg['compo'])
            GAME.publish_admin(type='info', msg="Teams changed")
        elif typ == 'score_change':
            GAME.updateScore(msg["team"], msg["inc"])
            GAME.publish_admin(type='info', msg="Team "+msg["team"]+" score changed!")
            

    def on_close(self):
        print "WebSocketAdminHandler.on_close : GAME admin", GAME.admin
        GAME.socket_admin_disconnected()
        print "no more admin ? ",GAME.admin

    def send_msg(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        self.write_message(msg)

# Websocket to player.
class WebSocketBuzzHandler(tornado.websocket.WebSocketHandler):
    
    def __init__(self,*args,**kwargs):
        
        tornado.websocket.WebSocketHandler.__init__(self, *args,**kwargs)
        self.player = None

    def open(self, *args, **kwargs):
        print("open", "WebSocketPlayerHandler")
        playerName = self.get_argument('user')
        GAME.set_socket(self, playerName)
        self.set_nodelay(True)
        GAME.publish_player(playerName, type='info', msg='Reference Timestamp : %d'%GAME.referenceTimeStamp)
    
    def on_message(self, message):
        msg = json.loads(message)
        if msg['type']=='buzz':
            print msg['when']
            GAME.publish_all(type='info', msg='%s buzzed %d'%(self.player,msg['when']))
            GAME.handle_buzz(self.player, int(msg['when']))
        
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



