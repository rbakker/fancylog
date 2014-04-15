fancylog
========
Fancy logging tool for python pipelines.

use:
import fancylog

logId = fancylog.addstep(workdir, ...)
fancylog.attachdata(workdir,logId, ...)

This will put log entries in the file
workdir/log_instance.js

To view log_instance.js in the browser,
make sure that both log_viewer.html
and json.js are copied to workdir,
then open log_viewer.html to view the log.

