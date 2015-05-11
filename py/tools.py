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
ch.setLevel(logging.INFO)
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


supported_extensions = {'audio':'mp3 mov wav'.split(),
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


AUDIO_SLIDE = """
<div id="slide" class="slide_audio %s">
    <center>
        <img  src="/static/img/sound.png"/>
    </center>
    <audio autoplay %s>
        <source src="/questions/%s" type="audio/mpeg">
        Your browser does not support the audio element.
    </audio>
</div>
"""

VIDEO_SLIDE = """
<div class="row">
    <div class="column twelve">
        <div id="slide" class="slide_video %s" %s>
            <center>
                <video width="80%%" autoplay>
                    <source src="/questions/%s" type="video/mp4" >
                </video>
            </center>
        </div>
    </div>
</div>
"""
IMAGE_SLIDE = """
<div id="slide" class="slide_image %s">
    <center>
        <img  src="/questions/%s"/>
    </center>
</div>
"""
TEXT_SLIDE = """
<div id="slide" class="slide_text %s">
    <center>
        %s
    </center>
</div>
"""


def get_q_type(ext):
  try:
    return question_type_map[ext]
  except KeyError:
    return None

def get_slide_preview(question, answer, question_id):
    return ("%d."%question_id)+get_slide_html(question, preview=True)+get_slide_html(answer, preview=True, cls="answer")

def get_slide_html(slide, preview=False, cls=""):
    content = video_opts = audio_opts = ""
    if preview:
        audio_opts = "muted"
        video_opts = "muted"

    if slide.text is not None :
        content += TEXT_SLIDE%(cls,slide.text)
    if slide.type == "image":
        content +=  IMAGE_SLIDE%(cls, slide.ref)
    elif slide.type == 'audio':
        content +=  AUDIO_SLIDE%(cls, audio_opts, slide.ref)
    elif slide.type=="video":
        content +=  VIDEO_SLIDE%(cls, video_opts, slide.ref)
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
            logger.debug( item)
            abs_item = os.path.join(path,item)
            section = {} 
              
            name = os.path.basename(abs_item)
            name_match = re_section_name.match(name)
            if not name_match:
                logger.debug(( "section name %s is not supported. Please correct"%name))
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
                logger.debug( name)
                name, qtyp = name.rsplit('.',1)
                qtyp = get_q_type(qtyp)
                if qtyp == "text":
                    with open(abs_item) as f:
                        for line in f:
                        # logger.debug(_html(line))
                            q, a = line.rstrip('\n').split(';')
                            question = slide(type="text", text=q, ref=None), slide(type="text", text=a, ref=None)
                            sec_questions.append(question)
            else:

                #first check if we have a config.json in the folder that contains complex questions stuff
                if os.path.exists(os.path.join(abs_item, "config.json")):
                    config = json.load(open(os.path.join(abs_item, "config.json")))
                    logger.debug( config)
                    for question, answer in config["questions"]:
                        #just a string
                        if not isinstance(question, (list,tuple)):
                            question = [question]
                        if not isinstance(answer, (list, tuple)):
                            answer = [answer]
                        if len(question)>2:
                            logger.debug( "skipping question %s, because too complex"%question)
                            continue
                        if len(answer)>2:
                            logger.debug( "skipping answer %s, because too complex"%answer)
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
                                logger.debug( "skipping question %s because file %s doesn't exist"%(question,qref))
                                continue
                            qref = os.path.relpath(qref, path)
                            qtyp = get_q_type(qref.rsplit('.',1)[-1])
                            if not qtyp:
                                logger.debug( "type %s not supported"%qref)
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
                                logger.debug( "skipping answer %s because file %s doesn't exist"%(answer,qref))
                                continue
                            aref = os.path.relpath(aref, path)
                            atyp = get_q_type(aref.rsplit('.',1)[-1])
                            if not atyp:
                                logger.debug( "type %s not supported"%aref)
                                continue
                        question = slide(type=qtyp, ref=qref, text=qtext), slide(type=atyp, ref=aref, text=atext)
                        logger.debug( question)
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
                                logger.debug( "more than one question or answer in directory")
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
                            name_match = re_question_name.match(sub_item)
                            if not name_match:
                                logger.debug(( "question name %s is not supported. Please correct"%sub_item))
                                continue
                            order, pts_gr, points, sname, qtype = groups = name_match.groups()
                            # logger.debug( order, pts_gr, points, sname, qtype)
                            qtype = qtype.lower()
                            qtyp = get_q_type(qtype)
                            if not qtyp:
                                logger.debug( qtype, "not supported")
                                continue

                            if qtyp == "text":
                                with open(abs_sub_item) as f:
                                    for line in f:
                                    # logger.debug(_html(line))
                                        q, a = line.rstrip('\n').split(';')
                                        question = slide(type="text", text=q, ref=None), slide(type="text", text=a, ref=None)
                                        sec_questions.append(question)
                            else:
                                sec_questions.append((slide(type=qtyp, ref=os.path.relpath(abs_sub_item, path), text=None), slide(type="text", text=os.path.basename(sname), ref=None)))

            if sec_questions:
                section["questions"] = []
                section["questions_previews"] = []
                for question, answer in sec_questions:
                    q = get_slide_html(question)
                    a = get_slide_html(answer)
                    if q and a:
                        section['questions'].append((q, a))
                        q_preview = get_slide_preview(question, answer, len(section['questions']))
                        section['questions_previews'].append(q_preview)
                    else:
                        logger.debug( question,"not ok")

                section["name"] = name

            if not section : continue
            self.sections.append(section)
            # logger.debug( section.questions)
            # logger.debug( '</ul>')
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
        <span class='huge'>%d</span></div>"""%(self.question_id+1)
            else:
                return self.sections[self.section_id]['questions'][self.question_id][self.question_status-1]

    def get_current_resume(self):
        if self.section_id == -1:
            return '<div id="slide" class="slide_text">BIG BUZZ</div>'
        return self.sections[self.section_id]['questions_previews'][self.question_id]
 

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




