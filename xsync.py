#!/usr/bin/env python
"""
xsync.py by zjx20
http://github.com/zjx20/xsync/

This script will watch a local directory and on change will
sync to a remote directory. The script can be easily modified
to do whatever you want on a change event.

requires: pip install watchdog

  about watchdog:
    # project site: http://github.com/gorakhargosh/watchdog
    # api document: https://pythonhosted.org/watchdog/index.html

TODO: enhance 'ignore list' feature
TODO: optimize copying a non-empty folder into the local folder
TODO: optimize deleting, just sync deletions
"""

import os, datetime, time
import sys, argparse, json
import watchdog.events, watchdog.observers

class SyncHandler(watchdog.events.FileSystemEventHandler):

    def __init__(self, conf):
        watchdog.events.FileSystemEventHandler.__init__(self)
        self.local_path = conf['local_path']
        self.remote_host = conf['remote_host']
        self.remote_path = conf['remote_path']
        self.ignore_list = []
        if conf.has_key('ignore_list'):
            self.ignore_list = conf['ignore_list']
        self.ignore_list += ['.xsync']    # ignore .xsync by default

    def should_ignore(self, filename):
        for ig in self.ignore_list:
            if ig in filename:
                return True
        return False

    def on_created(self, event):
        filename = event.src_path
        if self.should_ignore(filename):
            return

        remote_file = filename.replace(self.local_path, '')
        remote_parent = os.path.dirname(remote_file)

        cmd = " rsync -cazq --delete %s %s:%s%s/ " % (filename,
                self.remote_host, self.remote_path, remote_parent)
        display("Syncing %s " % filename)
        os.system(cmd)

    def on_deleted(self, event):
        filename = event.src_path
        if self.should_ignore(filename):
            return

        local_parent = os.path.dirname(filename)
        if not os.path.isdir(local_parent):
            # the parent dir does not exists too
            return

        remote_file = filename.replace(self.local_path, '')
        remote_parent = os.path.dirname(remote_file)

        cmd = " rsync -cazq --delete %s/ %s:%s%s/ " % (local_parent,
                self.remote_host, self.remote_path, remote_parent)
        display("Syncing %s " % filename)
        os.system(cmd)

    def on_modified(self, event):
        if isinstance(event, watchdog.events.DirModifiedEvent):
            # ignore dir modified event
            return

        filename = event.src_path
        if self.should_ignore(filename):
            return

        remote_file = filename.replace(self.local_path, '')

        cmd = " rsync -cazq --delete %s %s:%s%s " % (filename,
                self.remote_host, self.remote_path, remote_file)
        display("Syncing %s " % filename)
        os.system(cmd)

    def on_moved(self, event):
        if event.is_directory:
            self.on_deleted(watchdog.events.DirDeletedEvent(event.src_path))
        else:
            self.on_deleted(watchdog.events.FileDeletedEvent(event.src_path))

        if os.path.dirname(event.src_path) == os.path.dirname(event.dest_path):
            return

        if event.is_directory:
            self.on_created(watchdog.events.DirCreatedEvent(event.dest_path))
        else:
            self.on_deleted(watchdog.events.FileCreatedEvent(event.dest_path))


def display(str):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print "[{0}] {1}".format(now, str)


def parse_opt():
    parser = argparse.ArgumentParser(prog='xsync',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--full', action='store_true',
            help='do full sync instead of starting a daemon')
    parser.add_argument('--conf', action='store',
            default=os.path.join(os.getcwd(), '.xsync'),
            help='config file path')
    args = parser.parse_args()
    return args


"""
Config sample:

  {
    "local_path": "/home/x/project1/",
    "remote_host": "dev@111.222.111.222",
    "remote_path": "/home/dev/project1/",
    "ignore_list": [".git", ".svn", ".DS_Store"]
  }

  #
  # NOTICE:
  #
  #   it will use dirname of config file path as 'local_path' if
  #   the field does not exists.
  #
  #   if you are meeting a non-standard ssh port, try
  #   "--rsh='ssh -p2222' x@127.0.0.1" as 'remote_host'.
  #
  #   'ignore_list' is optional.
  #

  Or config blocks in an array

  [
    {
      "local_path": "/home/x/project1/",
      "remote_host": "dev@111.222.111.222",
      "remote_path": "/home/dev/project1/",
      "ignore_list": [".git", ".svn", ".DS_Store"]
    },
    {
      ...
    },
  ]
"""
def parse_conf(filepath):
    if not os.path.isfile(filepath):
        print >> sys.stderr, '[WARNING] Config "' + filepath + '" not ' + \
                'exists! skipped.'
        return []

    conf = None
    with open(filepath) as f:
        try:
            conf = json.loads(f.read())
        except ValueError:
            print >> sys.stderr, '[WARNING] Couldn\'t parse config ' + \
                    'from "%s"! skipped.' % filepath
            return []

    conf_list = conf
    if not isinstance(conf, list):
        conf_list = [conf]

    for conf in conf_list:
        if not conf.has_key('local_path'):
            conf['local_path'] = '%s/' % os.path.dirname(
                    os.path.abspath(filepath))

    return conf_list

def watch(conf_list):
    observer = watchdog.observers.Observer()

    for conf in conf_list:
        observer.schedule(SyncHandler(conf), conf['local_path'], recursive=True)
        display('Watching for local path "%s".' % conf['local_path'])

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def full_sync(conf_list):
    for conf in conf_list:
        display("Full sync from '%s' to %s:%s" % (conf['local_path'],
                conf['remote_host'], conf['remote_path']))
        cmd = " rsync -cazqr --delete %s %s:%s " % (conf['local_path'],
                conf['remote_host'], conf['remote_path'])
        print cmd
        os.system(cmd)

def main():
    args = parse_opt()
    conf_list = parse_conf(args.conf)

    if len(conf_list) == 0:
        return

    if args.full:
        full_sync(conf_list)
    else:
        watch(conf_list)

if __name__ == '__main__':
    main()