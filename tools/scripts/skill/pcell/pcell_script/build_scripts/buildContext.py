#!/usr/intel/bin/python2.5.2 -E
import os, tempfile, sys, subprocess
from optparse import OptionParser
from string import Template

# get options

parser = OptionParser()
parser.usage = "usage:  buildContext.py [options] <file1|dir1> [...<fileN|dirN>]"
parser.add_option("-c", "--context", dest="context", action="store", type="string", help="Name of context", metavar="CONTEXT", default="test")
parser.add_option("-r", "--recursive", dest="recursive", default=False, action="store_true", help="Descend directories recursivly to look for files.")
parser.add_option("-s", "--suffix", dest="suffix", action="append", help = "Suffix for source file, like \".il\" (multiple -s <suffix> options are OK)",default=[])
parser.add_option("-l", "--logfile-directory", dest="logfile_dir", action = "store", help = "Log file directory", default='.')
parser.add_option("-n", "--negative-check", dest="negcheck", default=False, action="store_true", help="Test Context file builder with auto-generated negative data")
parser.add_option("-z", "--expect-failure", dest="expect_failure", default=False, action="store_true", help="This run is expected to fail (for testing negative check)")

def findFiles( path, recursive, suffixes):
    flist = []
    if not recursive:
        files = os.listdir(path)
        for filename in files:
            if os.path.splitext(filename)[1] in suffixes:
                flist.append(os.path.join(path, filename))
        return flist
    else:
        for root, dirs, files in os.walk(path):
            for filename in files:
                if os.path.splitext(filename)[1] in suffixes:
                    flist.append(os.path.join(root, filename))
            
    return flist

def writeSkillCmdFile(context, filelist):
    cmdfile = "/tmp/buildContext" + str(os.getpid()) + ".il"
    
    contextfile = os.path.abspath(context) + '.cxt'
    print "Writing skill cmd file:", cmdfile
    try:
        fh = open(cmdfile, 'w')
    except:
        print "Could not create skill cmd file", cmdfile
        sys.exit(1)
    else:
        print >>fh, 'setContext.autoload = \"skillDev.cxt\";';
        print >>fh, 'saveContext.autoload = \"skillDev.cxt\";';
        print >>fh, 'let( ()'
        print >>fh, '    (sstatus writeProtect t)' 
        print >>fh, "    setContext(\"%s\")"%(context)
        for f in filelist:
            print >>fh, "    println(\"%s\")"%("Loading " + f)
            print >>fh, "    unless( errset( load(\"%s\") t) exit(1))"%(f)
        print >>fh, "    unless( errset(saveContext(\"%s\") t) exit(1))"%(contextfile)
        print >>fh, '    (sstatus writeProtect nil)' 
        print >>fh, ")" 
        print >>fh, "exit(0)"
        fh.close()
    return [contextfile, cmdfile]
##################

(options, args) = parser.parse_args()
filelist = []
    
if options.negcheck:
    print args
    skillfile = "/tmp/negativeskill" + str(os.getpid()) + ".il"
    f=open(skillfile, 'w')
    f.write("Hi Mom!")
    f.close()
    os.chmod(skillfile, 0755)
    
    args = [skillfile]
    options.logfile_dir = "./badlog"
    options.context = "./badcxt"
    options.suffix = [".il"]
    options.recursive = False
    options.expect_failure = True
    
    
    
    print options
   # cmd = "../build_scripts/buildContext.py  -z -l ./badlog -s .il -c badcxt " + skillfile
   # print cmd
   # os.system( cmd)
   # sys.exit(0)

recursive = options.recursive
if options.suffix:
    suffixes = options.suffix
else:
    suffixes = [".il", ".ile"]
if not args:
    print parser.usage
    print "Try \"buildContext.py -h\" for more info."
    sys.exit(0)

for path in args:
    if os.path.isfile(path) and os.path.splitext(path)[1] in suffixes:
        filelist.append(path)
    elif os.path.isdir(path):
        filelist.extend( findFiles( path, recursive, suffixes))
    else:
        print "Argument \"%s\" does not exist or is not readable" %(path)
        sys.exit(1)

if not filelist:
    print "ERROR: No files found given: ", args
    sys.exit(1)

else:
    [contextfile, skillfile] = writeSkillCmdFile(options.context, filelist)
    if os.path.isfile(contextfile):
        print "Deleting old 32-bit: ", contextfile
        try:
            os.unlink( contextfile)
        except:
            print "Could not delete old 32-bit", contextfile
            sys.exit(1)    
                   
    
    (head, tail) = os.path.split( contextfile)
    cxt64 = os.path.join( head, "64bit", tail)
    if os.path.isfile(cxt64):    
        print "Deleting old 64-bit:", cxt64
        try:
            os.unlink( cxt64)
        except:
            print "Could not delete old 64-bit", contextfile
            sys.exit(1)    
                   

    (context_filedir, actual_context_file) = os.path.split(contextfile)
    if not os.path.isdir( context_filedir):
        print "No such directory!", context_filedir
        sys.exit(1)
    
    logfile_dir =  os.path.abspath( options.logfile_dir)
    print "Logfile directory:", logfile_dir
  
    if not os.path.isdir( logfile_dir):
        print "Creating:", logfile_dir
        try:
            os.makedirs(logfile_dir)
        except:
            print "Could not create log file directory: ", logfile_dir
            sys.exit(1)
   
    base_context = os.path.basename(options.context)
    shellinfo  = { 'logfile_32' : os.path.join(logfile_dir, base_context+".cxt32.log"),
                'logfile_64' : os.path.join(logfile_dir, base_context + ".cxt64.log"),
                'skillfile'  : skillfile, 'PBG': '$!'}
  #  print shellinfo     
    print "Building Context file %s..." %(contextfile)
    cmdstring = Template("""#!/bin/csh -f
    #set verbose
    \\rm -f $logfile_32 $logfile_64
    date
    $${CDSHOME}/tools/dfII/bin/dbAccess -32 -load $skillfile >& $logfile_32 &
    $${CDSHOME}/tools/dfII/bin/dbAccess -64 -load $skillfile >& $logfile_64 &
    wait
    if( $$? == 1 ) then
        exit 1
    endif
 
    
    """).substitute(shellinfo)
  
    cmdfile = "/tmp/buildContext" + str(os.getpid()) + ".csh"
    f=open(cmdfile, 'w')
    f.write(cmdstring)
    f.close()
    os.chmod(cmdfile, 0755)
    result = subprocess.call([cmdfile], shell=True)
    os.unlink(skillfile)
    os.unlink(cmdfile)
    expected_result = ""
    if options.expect_failure:
        expected_result = "NEGATIVE CHECK -- Failure is EXPECTED"
   
        
    if result:
        print "Context file build FAILED (shell script to launch dbAccess returned 1)."
        sys.exit(1)
    else:
        (head, tail) = os.path.split( contextfile)
        cxt64 = os.path.join( head, "64bit", tail)
        if os.path.isfile(contextfile):
            print "Context file (32 bit)", contextfile, "was created."
            if options.expect_failure:
                print "NEGATIVE CHECK FAILED!  Was there really bad SKILL?"
                sys.exit(1)
        else: 
            print "Context file build FAILED. %s\n32-bit file %s not created." %(expected_result, contextfile)
            sys.exit(1)
        if os.path.isfile(cxt64):
            print "Context file (64 bit)", cxt64, "was created."
        else: 
            print "Context file build FAILED. %s\n64-bit file %s not created." %(expected_result, contextfile)
            sys.exit(1)
        

 
        print "Done."
    
    sys.exit(0)

    
          
        

