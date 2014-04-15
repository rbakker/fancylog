#!/usr/bin/env python
import os.path as op
import json
import datetime
import subprocess
import argparse
import xml.etree.ElementTree as ET

# global variables that capture output based on logId
output = {}
parsed = {}
starttime = {}

# internal global variable to store dolog entries
_dolog = {
  'step': True,
  'stdout': True,
  'data': True,
  'nifti': True
}


# check whether logging is on for a given category
"""
The categories of dolog() that are used by fancylog internally
are listed above. External modules can add to this.
"""
def dolog(catg, onoff=None):
  global _dolog
  if onoff is not None:
    _dolog[catg] = onoff
  return _dolog[catg]


# internal routine check whether to not attach data to a log entry
def _donotattach(catg,force,logId):
  global _dolog
  return logId is None or (not _dolog[catg] and not force)


# initialize the log, should be called once before using fancylog.
def initlog(workdir)
  prepdir(workdir)
  logfile = op.join(workdir,'log_instance.js')
  print 'Create new LOG file "'+logfile+'"'
  with open(logfile, "w") as log:
    log.write('log=[];\n\n') 


# Add a processing step to the logfile, without executing it
def addstep(workdir, parentCmd,cmd,opts, title=None,force=False):
  if not force and not _dolog['step']: return None

  global starttime

  # use current filesize as id
  logId = getnextlogid(workdir)
  starttime[logId] = datetime.datetime.now()

  if title is None: title = cmd
  if parentCmd and op.isfile(parentCmd): parentCmd = file2prog(parentCmd)
  params = {
    'id': logId,
    'title': title,
    'parentCmd':parentCmd,
    'cmd':cmd,
    'opts':opts,
    'timestamp':starttime[logId].isoformat()
  }

  # prepare opts for json-dumping
  for opt in opts:
    try:
      opt[1] = "{}".format(opt[1])
    except:
      opt = "{}".format(opt)

  # write entry to logfile
  logfile = op.join(workdir,'log_instance.js')
  with open(logfile,"a") as log:
    log.write('log.push('+json.dumps(params,indent=2)+')\n\n')

  return logId


# Return the logid that will be used by the next addstep
def getnextlogid(workdir):
  logfile = op.join(workdir,'log_instance.js')
  # use current filesize as id
  return op.getsize(logfile)


# Attach data to a previously defined step
def attachdata(workdir, logId,name,result, type='string',force=False):
  if _donotattach('data',force,logId): return None

  if type=='file':
    result = op.normpath(result)

  params = {
    'attachTo':logId,
    'name':name,
    'result':result,
    'type':type
  }  
  logfile = op.join(workdir,'log_instance.js')
  with open(logfile,"a") as log:
    log.write('log.push('+json.dumps(params,indent=2)+')\n\n')      


# Execute a python module that supports the apply_argument_parser method
# and update the logfile
def runmodule(workdir, parentFile,moduleName,module,arglist, title=None):

  # combine unchecked arguments
  opts = [' '.join(['{}'.format(arg) for arg in arglist])]
  logId = addstep(workdir, op.splitext(op.basename(parentFile))[0],moduleName,opts, title=title)

  # checked arguments
  args = module.apply_argument_parser(arglist)
  opts = args2opts(args)
  attachdata(workdir, logId,'Parsed arguments',opts, type='opts')
      
  # store parsed arguments
  global parsed
  parsed[logId] = vars(args)

  try:
    ans = module.run(args)
    attachdata(workdir, logId,'Elapsed time','{}'.format(datetime.datetime.now()-starttime[logId]), type='time')
  except:
    import sys
    msg = str(sys.exc_info()[0])
    attachdata(workdir, logId,'Execution failed',msg)
    raise

  # capture output
  global output
  output[logId] = ans

  return logId


# Internal routine
def _runlogproc(cmd, workdir,logId):
  from sys import stdout 
  ans = None
  try:
    print 'Calling:\n'+' '.join(cmd)+'\n'
    stdout.flush()
    ans = subprocess.check_output(cmd, shell=False, stderr=subprocess.STDOUT)
    attachdata(workdir, logId,'Elapsed time','{}'.format(datetime.datetime.now()-starttime[logId]), type='time')
    # log output
    if dolog('stdout') and logId:
      if len(ans)>512:
        prepdir(workdir,'fancylog')
        outfile = op.join('fancylog','stdout_{}.txt'.format(logId))
        with open(op.join(workdir,outfile),"w") as fp:
          fp.write(ans)      
        attachdata(workdir, logId,'Standard output',outfile, type='file')
      elif len(ans)>0:
        attachdata(workdir, logId,'Standard output',ans, type='text')

  except subprocess.CalledProcessError as e:
    msg = 'Subprocess "'+e.cmd[0]+'" returned code '+str(e.returncode)+'.\nCommand: "'+' '.join(e.cmd)+'"\nMessage: "'+e.output+'"'
    attachdata(workdir, logId,'Execution failed',msg)
    raise Exception(msg)

  # capture output
  global output
  output[logId] = ans

  return logId


# Internal routine
def _skiplogproc(cmd, workdir,logId,whyskip=''):
  print 'Skipping:\n'+' '.join(cmd)+'\n'
  attachdata(workdir, logId,'Execution skipped',whyskip)


# Extract program name from script file name
def file2prog(f):
  return op.splitext(op.basename(f))[0]


# Execute an external command and update the logfile.
# cmd is an array which contains both
# the program name and its arguments, to be passed on 
# directly to the subprocess module
def runcommand(workdir, parentFile,cmd,skip=False, title=None):
  logId = addstep(workdir, parentFile,cmd[0],[' '.join(cmd)], title=title)
  if skip:
    _skiplogproc(cmd, workdir,logId)
  else:
    _runlogproc(cmd, workdir,logId)
  return logId


# Execute an external program and update the logfile.
# prog refers to the executable,
# and opts to its arguments, which can be 
# - strings, for positional arguments
# - arrays, for key-value arguments
def runprogram(workdir, parentFile,prog,opts,skip=False, whyskip='Using previous result',title=None):
  logId = addstep(workdir, parentFile,prog,opts, title=title)
  
  # prepare subprocess
  cmd = [prog]
  for kv in opts:
    if isinstance(kv, basestring): 
      cmd.append(kv)
    else:
      cmd.extend(kv)

  if skip:
    _skiplogproc(cmd, workdir,logId,whyskip)
  else:
    _runlogproc(cmd, workdir,logId)
  return logId  


# Convert args dictionary to list of {keys or key-value pairs}
def args2opts(args):
  args = vars(args)
  opts = []
  for k,v in args.iteritems():
    if not v==None:
      if isinstance(v,ET.Element):
        opts.append([k,ET.tostring(v)])
      elif v == "":
        opts.append('{}'.format(k))
      else:
        opts.append([k,'{}'.format(v)]) 

  return opts


# Prepare directory: multi-level mkdir, check if not exists
def prepdir(workdir,subdir=None,subsubdir=None):
  import os
  full = workdir
  if subdir:
    full = op.normpath(op.join(full,subdir))
  if subsubdir:
    full = op.normpath(op.join(full,subsubdir))

  if not op.exists(full):
    os.makedirs(full)

  return full


# Attach result of type 'nifti', ready for viewing in xtk
def attachnifti(workdir, logId,niifile,title,colormap=None,force=False):
  if _donotattach('nifti',force,logId): return None

  storedir = op.join(workdir,'fancylog')
  prepdir(storedir)

  import numpy as np
  import nibabel as nib
  base = op.basename(niifile).replace('.nii','_{}.nii').format(logId)
  saveAs = op.join(storedir,base)
  nii = nib.load(niifile)
  dim = nii.get_header()['dim']
  tp = tp0 = nii.get_data_dtype()
  if np.issubdtype(tp0,np.float64):
    # convert to float32, otherwise the xtk-viewer can't handle it
    img = nii.get_data().astype(np.float32)
    q = nii.get_affine()
    nii = nib.Nifti1Image(img,q)
    saveAs = saveAs.replace('.nii','_f32.nii')
    nib.save(nii,saveAs)
    tp = img.dtype
  else:
    # move data to storedir
    try:
      import os
      os.link(niifile,saveAs)
    except:
      import shutil
      shutil.copy(niifile,saveAs)

  scene = {
    'file': op.relpath(saveAs,workdir),
    'orig_dtype':'{}'.format(tp0),
    'dtype':'{}'.format(tp),
    'dims':dim[1:dim[0]+1].tolist()
  }

  if colormap:
    base = base.replace('.gz','').replace('.nii','_map.txt')
    saveAs = op.join(storedir,base)
    with open(saveAs,"w") as fp:
      i = 0;
      for line in colormap:
        fp.write(str(i)+' '+' '.join(map(str, line))+'\n')
        i += 1
    scene['colormap'] = op.relpath(saveAs,workdir)

  return attachdata(workdir, logId,title,scene, type='nifti')

# colormap: yellow foreground, transparent background
def colormapFgBg():
  return [
    ['Background',0,0,0,0],
    ['Foreground',255,255,0,255],
  ]


# colormap with transparent background, and five
# foreground colors that form the RUGBY acronym
def colormapRUGBY():
  return [
    ['Background',0,0,0,0],
    ['Label1',255,  0,  0,255], # Red
    ['Label2', 18, 10,143,255], # Ultramarine
    ['Label3',  0,255,  0,255], # Green
    ['Label4',  0,  0,255,255], # Blue
    ['Label4',255,255,  0,255]  # Yellow
  ]

