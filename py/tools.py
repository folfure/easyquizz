import re
import os
import logging


# create logger with 'spam_application'
logger = logging.getLogger('quizz')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
# fh = logging.FileHandler('quizz.log')
# fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
# logger.addHandler(fh)
logger.addHandler(ch)


def print_html(*stuff):
  print ' '.join([str(s) for s in stuff])+'<br/>'

def set_logger_debug():
  ch.setLevel(logging.DEBUG)



class Options:
    def __init__(self, **entries): 
      for k,v in entries.iteritems():
        self.__dict__[k] = v.value
    def __getattr__(self, attr):
      try:
        return self.__dict__[attr]
      except:
        return None



DEFAULT_POINTS = 4
re_section_name = re.compile(r"([0-9]{2})\.([a-zA-Z0-9_\.\ ]+)([0-9]+pts){0,1}")
re_question_name = re.compile(r"([0-9]+\.){0,1}(([0-9]+)pts\.){0,1}([a-zA-Z0-9_ -\[\]\(\).]+)\.([a-zA-Z0-9]+)")



class Question(object):
  def __init__(self, path):
    self.path = path
    name = os.path.basename(path)
    name_match = re_question_name.match(name)
    if not name_match:
      print_html( "question name %s is not supported. Please correct"%name)
      return
    order, pts_gr, self.points, self.name, self.ext = groups = name_match.groups()

    if self.points is None:
      self.points = 1
    self.points = int(self.points)

  def __repr__(self):
    return "%s(path='%s', name='%s',points=%d)"%(self.__class__.__name__, self.path, self.name, self.points)

  def html(self):
    return ""
  def source(self):
    return self.path


class TextQuestion(Question):
  def __init__(self,path, question):
    Question.__init__(self, path)
    self.question, self.answer=question.split(';')

  def html(self):
    return "<div id='question_fr' class='text_question' width='100%%' height='100%%'> %s ? </div>"%self.question.rstrip('? ')

  def source(self):
    return self.question


class VideoQuestion(Question):
  def __init__(self,path):
    Question.__init__(self, path)
  def html(self):
    return """
    <center><video width="80%%" autoplay id="question_fr">
  <source src="%s" type="video/mp4" >
</video></center>
    """%self.path


class ImageQuestion(Question):
  def __init__(self,path):
    Question.__init__(self, path)
  def html(self):
    return "<img width='100%' height='100%' src='%s'/>"%self.path


class MusicQuestion(Question):
  types = {"mp3":"mpeg"}
  def __init__(self, path):
    Question.__init__(self, path)
  def html(self):
    return """<audio autoplay id='question_fr'>
  <source src="%s" type="audio/mpeg">
Your browser does not support the audio element.
</audio>"""%self.path


supported_extensions = {MusicQuestion:'mp3'.split(),
            VideoQuestion:'mp4 mkv mpg mpeg avi'.split(),
            ImageQuestion:'jpeg jpg png tiff bmp pdf'.split(),
            TextQuestion:'txt csv'.split()
            }
question_type_map = {}
for k,v in supported_extensions.iteritems():
  for ext in v:
    question_type_map[ext]=k


def get_q_type(filename):
  ext = os.path.splitext(filename)[-1].lower()[1:]
  logger.debug("%s %s",filename,ext)
  try:
    return question_type_map[ext]
  except KeyError:
    return None


def create_questions(path):
  questions = []
  # print "creating questions<ul>"
  question_type = None
  for item in os.listdir(path):
    abs_item = os.path.join(path, item)
    if os.path.isdir(abs_item) or os.path.isfile(abs_item) :
      # print "<li>",item
      questions+=create_question(abs_item)
      if not questions:
        continue
      if question_type is None :
        question_type = type(questions[-1])
      elif type(questions[-1]) is not question_type:
        questions.pop()
    else:
      logging.error("%s : Symlinks not supported. Please provide files or directories")

  # print "</ul>"
  return questions

# scan a question file/dir and create question object 

def create_question(path):
  q = []
  if os.path.isdir(path):
    q_type=None
    files=[]
    # check all files are of the same type
    ff = os.listdir(path)
    if ff:
      for f in ff:
        abs_f = os.path.join(path,f)
        if not os.path.isfile(abs_f):
          logger.warning("question subitem %s will be skipped since it is not a file"%(abs_f))
          continue
        typ = get_q_type(f)
        if typ is None :
          logger.warning("question subitem %s will be skipped since it ha no valid type"%(abs_f))
          continue
        if q_type is not None and typ != q_type:
          logger.warning("%s contains non uniform question types '%s' vs '%s' (%s)"%(path, q_type, typ, f))
        else:
          q_type = typ
        files.append(abs_f)
      q.append(q_type(name=path,files=files))
    
  elif os.path.isfile(path):
    logger.debug("%s",path)
    q_type = get_q_type(path) 
    if q_type==TextQuestion:
      with open(path) as f:
        for line in f:
          # print_html(line)
          q.append(TextQuestion(path=path, question=line))
    elif q_type is not None:
      q.append(q_type(path))
  return q



class Section(object):
  def __init__(self,path):
    name = os.path.basename(path)
    name_match = re_section_name.match(name)
    # if not name_match:
      # print_html( "section name %s is not supported. Please correct"%name)
    groups = name_match.groups()
    self.id, self.name = groups[:-1]
    if len(groups)==2:
      self.weight = int(groups[-1])
    else:
      self.weight = 1
    self.id = int(self.id)
    self.questions = create_questions(path)
  def get_contents(self):
    return [i.source() for i in self.questions]




def create_sections(path):
  # print "creating sections...<ul>"
  sections = []

  for item in os.listdir(path):
    # print '<li>',item
    abs_item = os.path.join(path,item)
    section = create_section(abs_item)
    if not section or not section.questions: continue
    sections.append(section)
    # print section.questions
  # print '</ul>'
  return sections


def create_section(path):
  # print_html( "scanning %s"%path)
  if not os.path.isdir(path):
    return None
  else:
    return Section(path)
