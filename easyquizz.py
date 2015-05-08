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

TITLE ='BIG BUZZ'
TEMPLATES = tornado.template.Loader("static/template")
class Game(object):
    
    TIMER_DURATION = 5          # time to answer a question in seconds
    
    def __init__(self, db_name):
        new_db = not os.path.exists(db_name)
        #sqlite3 database
        self.db_conn = sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        #cursor for making queries to sql db
        self.cursor = self.db_conn.cursor()
		# map of player name to websocket {playerName: socketObject}
        self.sockets = dict()
        # map of player name to team name {playerName: teamName}
        self.players = dict()
        # map of team names to player set {teamName: set([players])}
        self.teams = dict()
        # websocket to screen display
        self.screens = []
        # map of team name to tuple (score, team name) {teamName: [score, teamName]}
        self.team_scores = dict()
        # map of player name to tuple (score, player name) {playerName: [score, playerName]}
        self.player_scores = dict()
        #admin web socket
        self.admin = None
        self.quizz_screen = tools.QuizzPlayer("questions")
        
        self.current_question_score = 5
        self.referenceTimeStamp = self.getCurrentTimestamp() # Timestamp UTC. 
        self.gameOpen = 10                      # contains 0 when game is closed. COntains a timestamp when game is open. Timestamp correspond to the time when the game was open. 
        self.can_answer = self.teams.keys()     # ALl the teams can answer at the beginning.
        self.cant_answer = []
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
                    print "adding " + player + " in " + team
        self.reset_buzzers()
    
    # Returns the current UTC timestamp. 
    #Maybe not accurate enough. Some systems gives timestamp with a second accuracy, not below.
    def getCurrentTimestamp(self):
        return int(round(time.time()*1000)) + time.timezone
    
    #Reactivate buzzers for the authorized teams.
    def reset_buzzers(self):
        self.publish_admin(type='info',msg="Resetting buzzers for authorized teams.")
        for team in self.can_answer:
            self.publish_team(team, type='buzzerActive', on=1)
        self.publish_admin(type='info',msg="Done.")
        self.check_status()
            
        

    # Triggered by game master at the end of the timer, when team that buzzed gives the wrong answer.
    # Team is excluded from the game for the current question.
    def je_dis_non(self):
        
        if not self.current_team or not self.current_player:
            self.publish_admin(type='info',msg="warning : no active team or player")
        else:
            print 'Wrong answer from '+self.current_team+", game continues."
            self.publish_all(type='info', msg='Wrong answer from '+self.current_team+", team excluded, games continue!")
            # Store team in can't answer team list.
            self.exclude([self.current_team])
            # Reactivate buzzers for the other to continue the same question.
            self.reset_buzzers()
            # Erase current_team and player.
            self.current_team = None
            self.current_player = None
        # Check if there are still teams in the game. Otherwise, close the game.
        
        if len(self.can_answer)==1 and self.can_answer[0]=="unassigned":
            self.closeGame()
        
        self.check_status()
        
    # Triggered by game master at the end of the timer, when team that buzzed gives the wrong answer.
    # Team score is increase by current question score and game is closed.
    def je_dis_oui(self):
        
        if not self.current_team or not self.current_player:
            self.publish_admin(type='info',msg="warning : no active team or player")
        else:
            print 'Right answer from '+self.current_team
            self.publish_all(type='info', msg='Right answer from '+self.current_team+"!!")
        
            # Increase current team and player score by question score.
            self.updateScore(self.current_team, self.current_question_score, self.current_player)
            #print self.player_scores
            self.closeGame()
        self.check_status()
        
        
    # Include teams in the current question.
    def include(self, teams):
        for team in teams:
            self.can_answer.append(team)
            self.cant_answer.remove(team)
    
    # Exclude teams from the current question.
    def exclude(self, teams):
        for team in teams:
            self.can_answer.remove(team)
            self.cant_answer.append(team)
    
    def activate_all_buzzers(self):
        self.can_answer = self.teams.keys()
        self.cant_answer = []
        self.reset_buzzers()
        self.publish_all(type='info', msg='Activating All Buzzers!')
        
    def deactivate_all_buzzers(self):
        self.can_answer = []
        self.cant_answer = self.teams.keys()
        self.reset_buzzers()
        self.publish_players(type='buzzerActive', on=0)
        self.publish_all(type='info', msg='Deactivating All Buzzers!')
            
    # returns True if Game is open and players can buzz.
    def isGameOpen(self):
        if self.gameOpen > 0:
            return True
        else:
            return False
    
    # Start the game. All teams can play.
    def start_game(self):
        self.gameOpen = self.getCurrentTimestamp()
        self.current_team = None
        self.current_player = None
        self.can_answer = self.teams.keys()
        self.reset_buzzers()
        self.publish_all(type='info', msg="Game starts!")
        
        
    def closeGame(self):
        self.gameOpen = 0
        self.current_team = None
        self.current_player = None
        #self.reset_buzzers()
        self.publish_all(type='info', msg='Game is over.')
    
    #to do
    def handle_buzz(self, player, timeBuzz):
        #self.reset_buzzers()
        playerTeam = self.players[player]
        self.current_team = playerTeam
        if playerTeam in self.can_answer and self.isGameOpen():
            # Player takes hand.
            # Block others buzzers
            self.publish_players(type='buzzerActive', on=0)
            self.publish_all(type='info', msg='All buzzers are blocked')
             
            self.current_team = playerTeam
            self.current_player = player
            self.publish_all(type='info', msg='Team %s has hand for 5 seconds'%playerTeam)
            self.publish_admin(type='buzzed', player=player)
            # start timer
            try:
                thread.start_new_thread( self.simpleTimer, (GAME.TIMER_DURATION, ) )
            except:
                print "Error: unable to start timer -> continue without timer."
        else:
            self.publish_all(type='info', msg='No effect buzz from %s'%player)
    
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
    
    # Returns scores list without unassigned team.
    def getScores(self):
        realTeamScores = self.team_scores
        # if unassigned team exist in realTeamScores, remove it.
        # This is to avoid problems in score rank. If unassigned exist, it appears in the ranking (1,2,4).
        if "unassigned" in realTeamScores.keys():
            del realTeamScores["unassigned"]
                
        return sorted(realTeamScores.values(),reverse=True)
    
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
    def updateScore(self, team, score_inc, player=None):
        if team in self.team_scores.keys():
            new_score = self.getTeamScore(team) + int(score_inc)
            self.setTeamScore(team, new_score) 
        if player is not None:  
            self.player_scores[player][0] += score_inc
        
        
    # Notifies all players and admin with scores.
    def notifyScores(self):
        scores = self.getScores()
        # Loop over players
        for player in self.sockets:
            team = self.players[player]
            self.publish_player(player, type='update_html', data={'scores':TEMPLATES.load("scores.html").generate(scores=scores, team=team)})
        self.publish_admin(type='update_html', data={'scores':TEMPLATES.load("scores_admin.html").generate(scores=scores, team="")})
    
    # Notifies admin with team composition.
    def notifyTeamsComposition(self):
        self.publish_admin(type='update_html', data={'team_composition':TEMPLATES.load("team_composition.html").generate(teams=self.teams.items())})
        
    
    def add_player(self,player,team="unassigned"):            
        t = self.add_team(team)
        t.add(player)
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
        self.notifyTeamsComposition()
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
    
    # Sets socket for player.
    def set_socket(self, socket, name):
        self.sockets[name] = socket
        socket.player = name

    # check state of player connections.
    def check_status(self):
        status = {}
        for player in self.players:
            if player in self.sockets.keys():
                # player has a socket.
                status[player] = "connected"
                if self.players[player] in self.can_answer: # if player's team can answer.
                # player can play
                    status[player] = "can_answer"
                else:
                    status[player] = "cant_answer"
            else:
                status[player] = "disconnected"
        self.publish_admin(type='player_status',data=status)
        
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

    def publish_screen(self, type, **kwargs):
        msg = dict(type=type)
        msg.update(kwargs)
        for screen in self.screens:
            screen.write_message(msg)

    def socket_disconnected(self, player):
        self.sockets.pop(player)
        self.publish_players(type='log',msg="User %s socket disconnected"%player)
        self.publish_admin(type='player_disconnected',name=player)
        self.check_status()

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
                    self.publish_admin(type='info', msg="%s changed team to %s"%(new_p,new_team))
                    print new_p, new_team
                    if self.publish_player(new_p, type='update_html', data={'scores':TEMPLATES.load("scores.html").generate(scores=scores, team=new_team)}):
                        self.publish_admin(type='info', msg="%s NEED RELOAD PAGE SINCE HIS TEAM CHANGED"%new_p)

                self.teams[new_team] = new_players

    def go_to_question(self, section_id, question_id):
        #to do deactivate buzzers ?
        self.publish_screen(type="update_html", data={'slides':self.quizz_screen.go_to_question(section_id, question_id)})
        self.update_admin_sections()

    def update_admin_sections(self):
        section_html = TEMPLATES.load("sections.html").generate(sections=self.quizz_screen.sections, 
                                                                section_id=self.quizz_screen.section_id, 
                                                                question_id=self.quizz_screen.question_id)
        self.publish_admin(type='update_html', data={'sections':section_html})
        

    def next_slide(self):
        self.publish_screen(type="update_html", data={'slides':self.quizz_screen.next_slide()})
        self.update_admin_sections()

    def next_question(self):
        self.publish_screen(type="update_html", data={'slides':self.quizz_screen.next_question()})
        self.update_admin_sections()


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
            GAME.create_player(self.current_user)
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


# Called when players connects to ipaddress. Either he never connects and he is redirected to /login.
# or he already connected and he is redirected to his buzz page. 
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
        GAME.check_status()

    def on_message(self, msg):
        if msg=="Keep alive": 
            print msg, "admin"
            return
        msg = json.loads(msg)
        typ = msg['type']
        if typ=='correct':
            GAME.publish_admin(type='info', msg='%s correct answer %.5f'%(self.player,msg['when']))
        elif typ=='teams_compo':
            GAME.update_teams_composition(msg['compo'])
            GAME.publish_admin(type='info', msg="Teams changed")
        elif typ == 'score_change':
            GAME.updateScore(msg["team"], msg["inc"])
            GAME.publish_admin(type='info', msg="Team "+msg["team"]+" score changed!")
        elif typ == "je_dis_oui":
            GAME.je_dis_oui()
        elif typ == "je_dis_non":
            GAME.je_dis_non()
        elif typ == "start_game":
            GAME.start_game()
        elif typ == "reset_buzzers":
            GAME.reset_buzzers()
        elif typ == "activate_all_buzzers":
            GAME.activate_all_buzzers()
        elif typ == "deactivate_all_buzzers":
            GAME.deactivate_all_buzzers()
        elif typ=="go_to_question":
            print "go_to_question",msg
            GAME.go_to_question(section_id=msg['sec_id'], question_id=msg['q_id'])
        elif typ=="next_slide":
            print "go_to_question",msg
            GAME.next_slide()

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
        print playerName + " Just Connected." 
        GAME.publish_all(type="info", msg="New Player Connected")
        GAME.check_status()
    
    def on_message(self, msg):
        if msg=="Keep alive": 
            print msg, self.player
            return
        msg = json.loads(msg)
        if msg['type']=='buzz':
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



