# -*- coding: utf-8 -*-
import re
import os
import logging
import glob
import pprint
import json
from collections import namedtuple

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
re_section_name = re.compile(r"([0-9]{2})\.([a-zA-Z0-9_\.\ '\-\_]+)([0-9]+pts){0,1}")
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

class Section(object):
  def __init__(self,path):
    pass
  def get_contents(self):
    return [i.source() for i in self.questions]


supported_extensions = {'audio':'mp3 mov'.split(),
            'video':'mp4 mkv mpg mpeg avi'.split(),
            'image':'jpeg jpg png tiff bmp pdf'.split(),
            'text':'txt csv'.split()
            }
question_type_map = {}
for k,v in supported_extensions.iteritems():
  for ext in v:
    question_type_map[ext]=k


#small namedtuple for holding slide stuff
slide = namedtuple('slide', ('type','text','ref'))


def get_q_type(ext):
  try:
    return question_type_map[ext]
  except KeyError:
    return None


def get_slide_html(slide):
    content = ""
    if slide.text is not None :
        content += '<div id="slide" class="slide_text"><center>%s</center></div>'%slide.text 
    if slide.type == "image":
        content +=  '<div id="slide" class="slide_image"><center><img  src="/questions/%s"/></center></div>'%slide.ref
    elif slide.type == 'audio':
        content +=  """<div id="slide" class="slide_audio"><center><img  src="/static/img/sound.png"/></center><audio autoplay>
  <source src="/questions/%s" type="audio/mpeg">
Your browser does not support the audio element.
</audio></div>"""%slide.ref
    elif slide.type=="video":
        content +=  """
            <div class="row"><div class="column eleven"><div id="slide" class="slide_video"><center><video width="80%%" autoplay>
          <source src="/questions/%s" type="video/mp4" >
        </video></center></div>
            """%slide.ref
    return content


class QuizzPlayer(object):
    NUMBER     = 0
    QUESTION   = 1
    ANSWER     = 2
    MAX_STATUS = 3

    def __init__(self, path):
        # print "creating sections...<ul>"
        self.section_id=-1
        self.question_id=-1
        self.question_status = self.NUMBER
        self.sections = []
        path = os.path.abspath(path)
        for item in sorted(os.listdir(path)):
            print item
            abs_item = os.path.join(path,item)
            section = {} 
              
            name = os.path.basename(abs_item)
            name_match = re_section_name.match(name)
            if not name_match:
                print( "section name %s is not supported. Please correct"%name)
                continue
            groups = name_match.groups()
            id, name = groups[:-1]
            if len(groups)==2:
                weight = int(groups[-1])
            else:
                weight = 1
            id = int(id)
            #iterate over items in sections folder
            sec_questions = []
            #if section if a text file
            if not os.path.isdir(abs_item):
                print name
                name, qtyp = name.rsplit('.',1)
                qtyp = get_q_type(qtyp)
                if qtyp == "text":
                    with open(abs_item) as f:
                        for line in f:
                        # print_html(line)
                            q, a = line.rstrip('\n').split(';')
                            question = slide(type="text", text=q, ref=None), slide(type="text", text=a, ref=None)
                            sec_questions.append(question)
            else:

                #first check if we have a config.json in the folder that contains complex questions stuff
                if os.path.exists(os.path.join(abs_item, "config.json")):
                    config = json.load(open(os.path.join(abs_item, "config.json")))
                    print config
                    for question, answer in config["questions"]:
                        #just a string
                        if not isinstance(question, (list,tuple)):
                            question = [question]
                        if not isinstance(answer, (list, tuple)):
                            answer = [answer]
                        if len(question)>2:
                            print "skipping question %s, because too complex"%question
                            continue
                        if len(answer)>2:
                            print "skipping answer %s, because too complex"%answer
                            continue
                        try:
                            qtext,qref=question
                        except:
                            qtext=question[0]
                            qref=None
                            qtyp="text"
                        else:
                            qref = os.path.abspath(os.path.join(abs_item,qref))
                            if not os.path.exists(qref):
                                print "skipping question %s because file %s doesn't exist"%(question,qref)
                                continue
                            qref = os.path.relpath(qref, path)
                            qtyp = get_q_type(qref.rsplit('.',1)[-1])
                            if not qtyp:
                                print "type %s not supported"%qref
                                continue
                        try:
                            atext,aref=answer
                        except:
                            atext=answer[0]
                            aref=None
                            atyp="text"
                        else:
                            aref = os.path.abspath(os.path.join(abs_item,aref))
                            if not os.path.exists(aref):
                                print "skipping answer %s because file %s doesn't exist"%(answer,qref)
                                continue
                            aref = os.path.relpath(aref, path)
                            atyp = get_q_type(aref.rsplit('.',1)[-1])
                            if not atyp:
                                print "type %s not supported"%aref
                                continue
                        question = slide(type=qtyp, ref=qref, text=qtext), slide(type=atyp, ref=aref, text=atext)
                        sec_questions.append(question)
                        
                else:
                    #if section is a directory we iterate over the files (simple questions) and subdirectories (complex questions)
                    for sub_item in sorted(os.listdir(abs_item)):
                        abs_sub_item = os.path.abspath(os.path.join(abs_item, sub_item))
                        #question is a directory (complex questiosn with answer type that may be different from text)
                        if os.path.isdir(abs_sub_item):
                            #find question.* and answer
                            questions = glob.glob(os.path.join(abs_sub_item,"question*.*"))
                            answers = glob.glob(os.path.join(abs_sub_item,"answer*.*"))
                            if not len(questions)==1 and not len(answers)==1:
                                print "more than one question or answer in directory"
                                continue
                            question = os.path.basename(questions[0])
                            answer = os.path.basename(answers[0])
                            quest, qtyp = question.rsplit(".", 1)
                            answ, atyp = answer.rsplit(".", 1)
                            q = quest.replace("question","").replace("_","'").lstrip('.')
                            a = answ.replace("answer","").replace("_","'").lstrip('.')
                            question = slide(type=get_q_type(qtyp), ref=os.path.relpath(questions[0], path), text=q), slide(type=get_q_type(atyp), ref=os.path.relpath(answers[0], path), text=a)
                            sec_questions.append(question)
                        else:
                            name_match = re_question_name.match(abs_sub_item)
                            if not name_match:
                                print( "question name %s is not supported. Please correct"%abs_sub_item)
                                continue
                            order, pts_gr, points, sname, qtype = groups = name_match.groups()
                            qtype = qtype.lower()
                            qtyp = get_q_type(qtype)
                            if not qtyp:
                                print qtype, "not supported"
                                continue

                            if qtyp == "text":
                                with open(abs_sub_item) as f:
                                    for line in f:
                                    # print_html(line)
                                        q, a = line.rstrip('\n').split(';')
                                        question = slide(type="text", text=q, ref=None), slide(type="text", text=a, ref=None)
                                        sec_questions.append(question)
                            else:
                                sec_questions.append((slide(type=qtyp, ref=os.path.relpath(abs_sub_item, path), text=None), slide(type="text", text=sname, ref=None)))

            if sec_questions:
                section["questions"] = []
                for question, answer in sec_questions:
                    q = get_slide_html(question)
                    a = get_slide_html(answer)
                    if q and a:
                        section['questions'].append((q, a))
                    else:
                        print question,"not ok"

                section["name"] = name

            if not section : continue
            self.sections.append(section)
            # print section.questions
            # print '</ul>'
        # pprint.pprint(self.sections)

    def go_to_question(self, section_id, question_id):
        self.section_id = section_id
        self.question_id = question_id
        self.question_status = self.QUESTION

        return self.get_current_content()
    def get_current_content(self):
        if self.section_id == -1:
            return '<div id="slide" class="slide_text">BIG BUZZ</div>'
        else:
            if self.question_status == self.NUMBER:
                return """<div id='slide' class='slide_text'>
        <h1>%d</h1></div>"""%self.question_id
            else:
                return self.sections[self.section_id]['questions'][self.question_id][self.question_status-1]


    def next_question(self):
        """
        get next question content
        """
        self.question_status = self.NUMBER
        #first try to get next question in same section
        #if we were at the intro page we go tho first question of first section
        if self.section_id == -1:
            self.section_id = 0
            self.question_id = 0
        else:
            self.question_id+=1
            if self.question_id >= len(self.sections[self.section_id]['questions']):
                self.question_id = 0
                self.section_id += 1
                if self.section_id >= len(self.sections):
                    self.section_id = -1 
                    self.question_id = -1
        return self.get_current_content()

    def next_slide(self):
        """
        return next slide content
        """
        self.question_status = (self.question_status+1)%self.MAX_STATUS
        if self.section_id == -1 or self.question_status == self.NUMBER:
            return self.next_question()
        else:
            return self.get_current_content()







def create_section(path):
  # print_html( "scanning %s"%path)
  if not os.path.isdir(path):
    return None
  else:
    return Section(path)


if __name__ == "__main__":
    QuizzPlayer("../questions")
