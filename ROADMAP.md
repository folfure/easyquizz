TO DO
=====
au revoir

1. Buzzers 
 - Add synchro timestamp between players and server when websocket is created and each time buzzers are reset
 - when user buzzes : 
    * check if he can buzz by checking the timestamp he sends is younger than the last reset (parasite buzz sent before the buzz button has been deactivated n the client side)
    * deactivate all other buzzers (javascript ) 
    * stop/hide video/image/question and display countdown on THE presentation screen
 - if good answer -> assign points and reset buzzers
 - if bad answer -> he personnaly is deactivated until next question and other teams can answer and his team is currently deacivated 

2. Misc.
 - correct admin problem when cookie and no logoff (seems already corrected)
 - put timer in javascript on client side to avoid consecutive click that could put server on knees

3. Questions
 - make template for questions and send to the other guys
 
2. Admin dashboard

  a. standard buttons
 - je dis oui : 
      . current user won, scores the points of the question for him and for his team, 
      . deactivate all buzzers
      . display rest of video / image / sound / question with on top answer
 - je dis non : 
      + other teams can answer
      + display rest of video / image / sound 
 - next button (like powerpoint):
      + go to next step (big question number or question itself or socres at end of section)
 - deactivate all buzzers (CARNOT)
 - activate all buzzers (CARNOT)

  b. status of all players
 - gray = not connected (no websocket)
 - white = activated (can buzz)
 - strikethrough = deactivated (cannot buzz)
 
  c. list of questions
 - toggle display sections 
 - list of questions
 - toggle question to display answer
 - current question + answer displayed somewhere
 - highlight of current question in the list
 - small button to display directly to this question to the users
 

  d. scores (CARNOT)
  - always displayed to THE screen somewhere
  - +/- buttons to add/substract points to the team

