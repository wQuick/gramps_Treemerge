#------------------------------------------------------------------------
#
# Find Possible Duplicate People
#
#------------------------------------------------------------------------

#import pip
#pip.main(['install', '--user', '--upgrade', '--break-system-packages', 'setuptools'])
#pip.main(['install', '--user', '--upgrade', '--break-system-packages', 'joblib'])
#pip.main(['install', '--user', '--upgrade', '--break-system-packages', 'sklearn'])
#pip.main(['install', '--user', '--upgrade', '--break-system-packages', 'scikit-learn'])

register(TOOL,
         id = 'treemerge',
         name = _("Merge 2 trees by matching persons"),
         description = _("Searches the entire database, looking for "
                         "individual entries that may represent the same person."
                         "Verify by viewing small tree around the matched persons."),
         version = '0.8beta',
         gramps_target_version = '5.2',
         status = STABLE,
         fname = 'treemerge.py',
         authors = ["Anders Ardo"],
         authors_email = ["Anders.Ardo@gmail.com"],
         category = TOOL_DBPROC,
         toolclass = 'TreeMerge',
         optionclass = 'TreeMergeOptions',
         tool_modes = [TOOL_MODE_GUI]
         )

