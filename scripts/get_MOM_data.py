#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, time
import siplib
import query
import re
import cPickle

import ssl

ssl._create_default_https_context = ssl._create_unverified_context

sip_cache = {}

#sip_cache_file = '/media/scratch/test/horneff/Pipeline-Test/feedback_test/sip_cache.pkl'
sip_cache_file = None

def init_cache(cache_file, create_if_needed=False):
    global sip_cache_file
    global sip_cache
    if os.path.exists(cache_file):
        print "Reading in SIP-cache..."
        with open(cache_file) as f:
            sip_cache = cPickle.load(f)
        print "Found %d SIPs in cache-file."%(len(sip_cache))
        sip_cache_file = cache_file
    elif (create_if_needed
          and os.path.isdir(os.path.dirname(cache_file))
          and os.access(os.path.dirname(cache_file),os.W_OK) ):
        sip_cache_file = cache_file
    else:
        raise ValueError("init_cache: cache-file does not exist!")

def get_dataID_from_filename(path, project, verbose=False):
    from common.database.Context import context
    from awlofar.config.startup import CorrelatedDataProduct,UnspecifiedDataProduct
    filename = os.path.basename(path)
    context.set_project(project)
    query = CorrelatedDataProduct.dataProductIdentifierName == filename
    for dprod in query:
        if verbose:
            print "Found dataID %s for file %s in Correlated-DataProducts"%(dprod.dataProductIdentifier,filename)
        return dprod.dataProductIdentifier
    query2 = UnspecifiedDataProduct.dataProductIdentifierName == filename
    for dprod in query2:
        if verbose:
            print "Found dataID %s for file %s in Unspecified-DataProducts"%(dprod.dataProductIdentifier,filename)
        return dprod.dataProductIdentifier    
    
def get_obsID_from_filename(path):
    filename = os.path.basename(path)
    obsReg = re.compile(r'L\d+')
    obsmatch = obsReg.match(filename)
    if (not obsmatch):
        print "get_obsID_from_filename: Could not find obs-ID in filename %s!"%(filename)
        raise ValueError("Could not find obs-ID in filename!")
    obsID = obsmatch.group(0)[1:]
    return obsID

def get_SIP_from_dataID(dpid, projectID, verbose=False):
    global sip_cache
    xml = query.getsip_fromlta_byprojectandltadataproductid(projectID, dpid)
    new_sip = siplib.Sip.from_xml(xml)
    filename = new_sip.sip.dataProduct.fileName
    sip_cache[filename] = new_sip
    return new_sip

def get_SIPs_from_obsID(obsID, projectID, verbose=False):
    if verbose:
        print "Downloading all SIPs for \"observation\" %s in project %s."%(obsID, projectID)
    dpids = query.getltadataproductids_fromlta_byprojectandsasid(projectID, obsID)
    if not dpids or len(dpids) < 1:
        print "get_SIPs_from_obsID: failed to get dataproduct-IDs for obs %s in project %s!"%(obsID, projectID)
    starttime = time.time()
    for (num,input_dpid) in enumerate(dpids):
        get_SIP_from_dataID(input_dpid, projectID, verbose)
        if verbose and ((num+1)%10)==0:
            duration = time.time()-starttime
            ETA = duration/(num+1)*(len(dpids)-num-1)
            print "read %d of %d SIPs, elapsed: %.2f seconds, ETA: %.2f seconds"%((num+1),len(dpids),duration,ETA)

def get_projectID_from_MSfile(path):
    import pyrap.tables as pt
    t = pt.table(path+"::OBSERVATION", readonly=True, ack=False)
    project = t.getcell('PROJECT',0)
    return project
            
def get_SIP_from_MSfile(path, dpID_mode="obsID", download_if_needed=True, verbose=False):
    if path[-1] == '/':
        path = path[:-1]
    filename = os.path.basename(path)
    nameparts = filename.split('.MS')
    if verbose and len(nameparts) < 2:
        print "get_SIP_from_MSfile: Filename \"%s\" does not look like a standard LOFAR MS file name. This may cause problems later on."%(filename)
    fileID = nameparts[0]
    strlen = len(fileID)
    for keyname in sip_cache.keys():
        if keyname[:strlen] == fileID:
            if verbose:
                print "Found SIP for %s in the cache"%(fileID)
            return sip_cache[keyname]
    if verbose:
        print "Cannot find SIP for %s in cache."%(filename)
    if not download_if_needed:
        raise ValueError("Cannot find SIP in cache and download is forbidden")
    projectID = get_projectID_from_MSfile(path)
    if dpID_mode.upper() == "OBSID":
        obsID = get_obsID_from_filename(filename)
        get_SIPs_from_obsID(obsID, projectID, verbose)
    elif dpID_mode.upper() == "LTA_NAME":
        dpID = get_dataID_from_filename(filename, projectID, verbose)
        get_SIP_from_dataID(dpID , projectID, verbose)
    else:
        raise ValueError("Unkonwn value for dpID_mode!: \""+str(dpID_mode)+"\"")
    if  sip_cache_file:
        with open(sip_cache_file,'w') as f:
            cPickle.dump(sip_cache,f,2)
    for keyname in sip_cache.keys():
        if keyname[:strlen] == fileID:
            if verbose:
                print "Found SIP for %s in the updated cache"%(fileID)
            return sip_cache[keyname]
    print "Cannot find SIP for %s in cache after downloading SIPs for obs %s!"%(filename, obsID)
    raise ValueError("Failed to download or identify SIP!")

    
