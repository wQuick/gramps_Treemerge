#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
# Copyright (C) 2008       Brian G. Matherly
# Copyright (C) 2010       Jakim Friant
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
"""Match persons RGD style."""

import sys
import os

# -------------------------------------------------------------------------
#
# GNOME libraries
#
# -------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import GooCanvas

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------

from gramps.gui.dialog import QuestionDialog2
from gramps.gen.merge import MergePersonQuery
from gramps.gen.merge.mergeeventquery import MergeEventQuery
from gramps.gui.glade import Glade
from gramps.gui.utils import ProgressMeter
from gramps.gui.plug import tool
from gramps.gen.soundex import soundex, compare
from gramps.gen.display.name import displayer as name_displayer
from gramps.gui.dialog import OkDialog
from gramps.gui.listmodel import ListModel
from gramps.gui.merge import MergePerson
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.dialog import RunDatabaseRepair
from gramps.gen.const import GRAMPS_LOCALE as glocale

from gramps.gen.errors import HandleError, MergeError  # By Waldemir Silva

# from libaccess import *
from matchview import ViewPersonMatch
from match import Match

_ = glocale.translation.sgettext

sys.path.append(os.path.abspath(os.path.dirname(__file__)))  # ??

# -------------------------------------------------------------------------
#
# Constants
#
# -------------------------------------------------------------------------
_val2label = {
     0.5: _("Low"),
    0.75: _("Medium"),
     0.9: _("High"),
}

_automergecutoff = {
  # 1.00: "1.00",
    0.99: "0.99",
    0.98: "0.98",
    0.97: "0.97",
    0.96: "0.96",
    0.95: "0.95",
    0.94: "0.94",
    0.93: "0.93",
    0.92: "0.92",
    0.91: "0.91",
    0.90: "0.90"
}

# WIKI_HELP_PAGE = '%s_-_Tools' % URL_MANUAL_PAGE
# WIKI_HELP_SEC = _('Find_Possible_Duplicate_People', 'manual')

# -------------------------------------------------------------------------
#
# The Actual tool.
#
# -------------------------------------------------------------------------


class TreeMerge(tool.Tool, ManagedWindow):  # CHECK use BatchTool when using automated merge

    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate

        tool.Tool.__init__(self, dbstate, options_class, name)
        self.uistate = uistate
        self.track = []
        ManagedWindow.__init__(self, self.uistate, self.track, self.__class__)
        self.dbstate = dbstate
        # init(self.dbstate.db)  # for libaccess
        self.map = {}
        self.list = []
        self.id_list = []
        self.index = 0
        self.merger = None
        self.mergee = None
        self.removed = {}
        self.dellist = set()
        self.length = len(self.list)
        self.p1 = None
        self.p2 = None
        self.progress = None
        top = Glade(toplevel="treemerge", also_load=["liststore1", "liststore2", "liststore3"])

        # retrieve options
        algoritm = self.options.handler.options_dict['algoritm']

        my_menu = Gtk.ListStore(str, object)
        for val in sorted(_val2label, reverse=True):
            my_menu.append([_val2label[val], val])

        # my_algmenu = Gtk.ListStore(str, object)
        #  for val in sorted(_alg2label, reverse=True):
        #     my_algmenu.append([_alg2label[val], val])

        my_automergecutoff = Gtk.ListStore(str, object)
        for val in sorted(_automergecutoff, reverse=True):
            my_automergecutoff.append([_automergecutoff[val], val])

        self.soundex_obj = top.get_object("soundex1")
        self.soundex_obj.set_active(0)  # Default value
        self.soundex_obj.show()

        self.menu = top.get_object("menu1")
        self.menu.set_model(my_menu)
        self.menu.set_active(0)

        algoritm = Gtk.ListStore(str, object)
        algoritm. append(["Ensemble", "ensemble"])
        algoritm. append(["SVM", "svm"])
        algoritm. append(["Score", "score"])
        self.algmenu = top.get_object("algoritm")
        self.algmenu.set_model(algoritm)
        self.algmenu.set_active(1)

        self.automergecutoff = top.get_object("automergecutoff")
        self.automergecutoff.set_model(my_automergecutoff)
        #self.automergecutoff.set_active(1)
        self.automergecutoff.set_active(0) # By Waldemir Silva

        mlist = top.get_object("mlist1")

        mtitles = [
            (_('Rating'), 3, 75),
            (_('First Person'), 1, 300),
            (_('Second Person'), 2, 300),
            ('', -1, 0)
        ]
        self.mlist = ListModel(mlist, mtitles, event_func=self.do_merge)

        self.infolbl = top.get_object("title3")
        window = top.toplevel
        self.set_window(window, top.get_object('title'),
                        _('Find/Merge Probably Identical Persons'))
        self.setup_configs('interface.duplicatepeopletool', 350, 220)
        infobtn = top.get_object("infobtn")
        infobtn.connect('clicked', self.info)
        matchbtn = top.get_object("matchbtn")
        matchbtn.connect('clicked', self.do_match)
        compbtn = top.get_object("cmpbtn")
        compbtn.connect('clicked', self.do_comp)
        notmatchbtn = top.get_object("notmatch")
        notmatchbtn.connect('clicked', self.do_notmatch)
        mergebtn = top.get_object("mergebtn")
        mergebtn.connect('clicked', self.do_merge)
        automergebtn = top.get_object("automerge")
        automergebtn.connect('clicked', self.do_automerge)
        automergebtn.set_tooltip_text('WARN automerge')
        closebtn = top.get_object("closebtn")
        closebtn.connect('clicked', self.close)

        self.compareview = None
        self.dbstate.connect('database-changed', self.redraw)  # ??
        self.db.connect("person-delete", self.person_delete)  # ??

        self.show()

    def notImplem(self, txt):
        self.infolbl.set_label("Control: %s - Not implemented yet" % txt)

    def infoMsg(self, txt):
        self.infolbl.set_label("Control: %s" % txt)

    def info(self, *obj):
        self.notImplem("Infobutton pressed")

    def on_help_clicked(self, obj):
        """Display the relevant portion of Gramps manual"""
        self.notImplem("Help")
        # display_help(WIKI_HELP_PAGE , WIKI_HELP_SEC)

    def do_notmatch(self, obj):
        store, select_line = self.mlist.selection.get_selected()
        if not select_line:
            self.infoMsg("Please select a match above")
            return
        (self.p1, self.p2) = self.mlist.get_object(select_line)
        self.dellist.add(self.p1)
        self.redraw()

    def do_match(self, obj):
        threshold = self.menu.get_model()[self.menu.get_active()][1]
        use_soundex = int(self.soundex_obj.get_active())
        algoritm = self.algmenu.get_model()[self.algmenu.get_active()][1]
        self.progress = ProgressMeter(_('Find matches for persons'),
                                      _('Looking for duplicate/matching people'),
                                      parent=self.window)

        matcher = Match(self.dbstate.db, self.progress, use_soundex, threshold, algoritm)
        try:
            matcher.do_find_matches()
            self.map = matcher.map
            self.list = matcher.list
        except AttributeError as msg:
            RunDatabaseRepair(str(msg), parent=self.window)
            return

        self.options.handler.options_dict['threshold'] = threshold
        self.options.handler.options_dict['soundex'] = use_soundex
        # Save options
        self.options.handler.save_options()
        self.length = len(self.list)

        if len(self.map) == 0:
            OkDialog(
                _("No matches found"),
                _("No potential duplicate people were found"),
                parent=self.window)
        else:
            self.redraw()
            self.show()  # ??

    def redraw(self):
        match_list = []
        for p1key, p1data in sorted(self.map.items(), key=lambda item: item[1][1], reverse=True):
            if p1key in self.dellist:
                continue
            (p2key, c) = p1data
            if p2key in self.dellist:
                continue
            if p1key == p2key:
                continue
            match_list.append((c, p1key, p2key))
        self.mlist.clear()
        for (c, p1key, p2key) in match_list:
            c1 = "%5.2f" % c
            c2 = "%5.2f" % (100-c)
            p1 = self.db.get_person_from_handle(p1key)
            p2 = self.db.get_person_from_handle(p2key)
            if not p1 or not p2:
                continue
            self.id_list.append((c, p1.gramps_id, p2.gramps_id))
            pn1 = name_displayer.display(p1)
            pn2 = name_displayer.display(p2)
            self.mlist.add([c1, pn1, pn2, c2], (p1key, p2key))

    def do_merge(self, obj):
        store, select_line = self.mlist.selection.get_selected()
        if not select_line:
            self.infoMsg("Please select a match above")
            return
        (self.p1, self.p2) = self.mlist.get_object(select_line)
        self.notImplem("Merge 2 matched persons")
        MergePerson(self.dbstate, self.uistate, self.track, self.p1, self.p2, self.on_update, True)

    def do_automerge(self, obj):
        cutoff = self.automergecutoff.get_model()[self.automergecutoff.get_active()][1]
        msg1 = 'Warning'
        label_msg1 = 'OK'
        label_msg2 = 'NO thanks'
        matches = []

        # sort by rating = c
        for p1key, p1data in sorted(self.map.items(), key=lambda item: item[1][1], reverse=True):
            if p1key in self.dellist:
                continue
            (p2key, c) = p1data
            if c < cutoff or p2key in self.dellist:
                continue
            if p1key == p2key:
                continue
            matches.append((p1key, p2key))

        msg2 = _('You are about to batch merge %d matches with rating above %s') % (len(matches), cutoff)
        res = QuestionDialog2(msg1, msg2, label_msg1, label_msg2).run()
        if not res:
            return  # False

        msg1 = _('Processing automerge') # By Waldemir Silva
        msg2 = _('You are about to batch merge %d matches with rating above %s') % (len(matches), cutoff)
        msg3 = _('Merging...')

        self.progress = ProgressMeter( msg1, msg2, True, parent=self.window) # By Waldemir Silva

        self.progress.set_pass(msg3, len(matches))

        for (p1key, p2key) in matches:
            try:
                if self.progress.step(): # by Waldemir Silva
                   break
                primary = self.dbstate.db.get_person_from_handle(p1key)
                secondary = self.dbstate.db.get_person_from_handle(p2key)
                query = MergePersonQuery(self.dbstate.db, primary, secondary)
                query.execute()
                person = self.dbstate.db.get_person_from_handle(p1key)
                self.cleanEventsFamilies(person)
            except HandleError:
                pass
                #print("An exception occurred:", type(error).__name__, "–", error)  # An exception occurred: Handle exception
            except MergeError as error: # by Waldemir Silv
                # handle the exception
                print("An exception occurred:", type(error).__name__, "–", error)  # An exception occurred: can't merge
            except Exception as error:   # by Waldemir Silva
                # handle the exception
                print("An exception occurred:",type(error).__name__, "–", error)  # An exception occurred: other exceptions
                #continue

        self.progress.close() # By Waldemir Silva

    def do_comp(self, obj):
        store, select_line = self.mlist.selection.get_selected()
        if not select_line:
            self.infoMsg("Please select a match above")
            return
        (self.p1, self.p2) = self.mlist.get_object(select_line)
        if self.compareview:
            self.compareview.close('')
        self.uistate.set_active(self.p1, 'Person')
        self.compareview = GraphComparePerson(
            self.dbstate, self.uistate, self.track, self.p1, self.p2, self.on_update, self.id_list)

    def on_update(self, handle_list=None):
        if self.db.has_person_handle(self.p1):
            titanic = self.p2
        else:
            titanic = self.p1
        self.dellist.add(titanic)
        self.redraw()

    def update_and_destroy(self, obj):
        self.close(obj)

    def close(self, obj, t=None):  # FIX
        if self.compareview:
            self.compareview.close('')
        ManagedWindow.close(self, *obj)

    def person_delete(self, handle_list):
        """ deal with person deletes outside of the tool """
        self.dellist.update(handle_list)  # add to dellist
        self.redraw()

    def __dummy(self, obj):
        """dummy callback, needed because a shared glade file is used for
        both toplevel windows and all signals must be handled.
        """

    def cleanEventsFamilies(self, person):
        """
        Cleanup person:
          Merges identical birth, death events
          Delete families with exactly 1 person and no events 
        """
        # Events
        birth = None
        death = None
        for evref in person.get_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(evref.ref)
            if event.get_type().is_birth():
                if birth:
                    birth = self.Merge(birth, event)
                else:
                    birth = event
            elif event.get_type().is_death():
                if death:
                    death = self.Merge(death, event)
                else:
                    death = event
        # Families
        for family_handle in (person.get_family_handle_list() + person.get_parent_family_handle_list()):
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if family:
                ant = len(family.get_child_ref_list())
                if family.get_father_handle():
                    ant += 1
                if family.get_mother_handle():
                    ant += 1
                if (ant == 1) and (len(family.get_event_ref_list()) == 0):
                    #delete family
                    family.set_father_handle(None)
                    family.set_mother_handle(None)
                    family.set_child_ref_list(None) #eller []

    def Merge(self, ev1, ev2):
        if not ev1:
            return ev2
        if ev1.are_equal(ev2):
            q = MergeEventQuery(self.dbstate, ev1, ev2)
            q.execute()
            return ev1
        dateOK = False
        placeOK = False
        phoenix = ev1
        titanic = ev2
        #
        if ev1.get_place_handle() == ev2.get_place_handle():
            placeOK = True
        if ev1.get_date_object().is_equal(ev2.get_date_object()):
            dateOK = True
        else:
            # use most complete date?
            best = ['ev1', 'ev2']
            if '00' in str(ev1.get_date_object()):
                best.remove('ev1')
            if '00' in str(ev2.get_date_object()):
                best.remove('ev2')
            if len(best) == 1:
                dateOK = True
                if best[0] == 'ev2':
                    phoenix = ev2
                    titanic = ev1                
        if dateOK and placeOK:
            q = MergeEventQuery(self.dbstate, phoenix, titanic)
            q.execute()
            return phoenix
        else:
            return ev1


class GraphComparePerson(ManagedWindow):

    def __init__(self, dbstate, uistate, track, p1, p2, callback, matches):
        self.uistate = uistate
        self.track = track
        ManagedWindow.__init__(self, self.uistate, self.track, self.__class__)
        self.update = callback  # = tool.on_update
        self.db = dbstate.db
        self.dbstate = dbstate
        self.p1 = p1
        self.p2 = p2

        top = Glade(toplevel="compgraph")
        window = top.toplevel
        self.set_window(window, top.get_object('title'), 'Graph Compare Potential Merges')
        self.setup_configs('interface.duplicatepeopletoolmatches', 800, 400)  # ?
        scrolled_win = top.get_object('scrwin')
        self.canvas = GooCanvas.Canvas()
        # self.canvas.connect("scroll-event", self.scroll_mouse)
        self.canvas.props.units = Gtk.Unit.POINTS
        self.canvas.props.resolution_x = 72
        self.canvas.props.resolution_y = 72
        scrolled_win.add(self.canvas)

        self.graphView = ViewPersonMatch(self.dbstate, self.uistate,
                                         self.canvas, track, self.p1, self.p2, callback, matches)

        self.closebtn = top.get_object("grclose")
        self.closebtn.connect('clicked', self.close)
        self.okbtn = top.get_object("grok")
        self.okbtn.connect('clicked', self.ok)
        self.okbtn.set_label("Merge")
        self.infobtn = top.get_object("grinfo")
        self.infobtn.connect('clicked', self.info)
        self.infobtn.set_label("Info - Not implemented")
        self.show()

    def close(self, obj, t=None):
        #=????????????????????
        try:
            ManagedWindow.close(self, *obj)
        except:
            pass

    def on_help_clicked(self, obj):
        """Display the relevant portion of Gramps manual"""
        # display_help(WIKI_HELP_PAGE , WIKI_HELP_SEC)

    def ok(self, obj):  # RENAME
        MergePerson(self.dbstate, self.uistate, self.track,
                    self.p1, self.p2, self.gr_on_update, True)

    def info(self, *obj):
        print('grinfo button clicked')

    def gr_on_update(self):
        self.close('')

    def update_and_destroy(self, obj):
        self.update(obj)
        self.close(obj)

    # Evt enable and just call close?
    # def person_delete(self, handle_list):
    #    """ deal with person deletes outside of the tool """
        # self.dellist.update(handle_list)
        # self.redraw()

    def __dummy(self, obj):
        """dummy callback, needed because a shared glade file is used for
        both toplevel windows and all signals must be handled.
        """

# ------------------------------------------------------------------------
#
#
#
# ------------------------------------------------------------------------


class TreeMergeOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)

        # Options specific for this report
        self.options_dict = {
            'soundex': 0,
            'threshold': 0.75,
            'algoritm': 'svm',
            'automergecutoff': 0.95
        }
        self.options_help = {
            'soundex': ("=0/1", "Whether to use SoundEx codes",
                        ["Do not use SoundEx", "Use SoundEx"],
                        True),
            'threshold': ("=num", "Threshold for tolerance",
                          "Floating point number")
        }
