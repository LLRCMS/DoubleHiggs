#! /usr/bin/env python
import sys, pwd, commands, optparse
import os
import re
import math
import string
from scipy.special import erf
from ROOT import *
import ROOT
from ConfigReader import *
from systReader import *


def parseOptions():

    usage = ('usage: %prog [options] datasetList\n'
             + '%prog -h for help')
    parser = optparse.OptionParser(usage)
    
    parser.add_option('-f', '--filename',   dest='filename',   type='string', default="",  help='input plots')
    parser.add_option('-o', '--dir', dest='outDir', type='string', default='', help='outdput dir')
    parser.add_option('-c', '--channel',   dest='channel', type='string', default='TauTau',  help='final state')
    parser.add_option('-i', '--config',   dest='config', type='string', default='',  help='config file')
    parser.add_option('-s', '--selection', dest='overSel', type='string', default='', help='overwrite selection string')
    parser.add_option('-r', '--resonant',  action="store_true",  dest='isResonant', help='is Resonant analysis')
    parser.add_option('-y', '--binbybin',  action="store_true", dest='binbybin', help='add bin by bins systematics')
    parser.add_option('-t', '--theory',  action="store_true", dest='theory', help='add theory systematics')
    parser.add_option('-u', '--shape', dest='shapeUnc', type='int', default=1, help='1:add 0:disable shape uncertainties')
    parser.add_option('--ws', dest='makeworkspace', default=False, action = 'store_true')


    # store options and arguments as global variables
    global opt, args
    (opt, args) = parser.parse_args()

def  writeCard(backgrounds,signals, select,region=-1) :

        variable = 'DNNoutSM_kl_1'

	theOutputDir = "{0}{1}".format(select,variable)
	dname = "_"+opt.channel+opt.outDir
	out_dir = "cards{1}/{0}/".format(theOutputDir,dname)

	cmd = "mkdir -p {0}".format(out_dir)
        
        regionName = ["","regB","regC","regD"]
	regionSuffix = ["SR","SStight","OSinviso","SSinviso"]
	status, output = commands.getstatusoutput(cmd)   
	thechannel = "2"
	if opt.channel == "ETau" : thechannel="1"
	elif opt.channel == "MuTau" : thechannel = "0"

	if "0b0j" in select : theCat = "0"
	if "2b0j" in select : theCat = "2"
	elif "1b1j" in select : theCat = "1"
	elif "boosted" in select : theCat = "3"
	elif "VBFloose" in select : theCat = "4"




	#read config
	categories = []
	categories.append((0,select))
	MCbackgrounds=[]
	processes=[]
	inRoot = TFile.Open(opt.filename)
	for bkg in backgrounds:
		#Add protection against empty processes => If I remove this I could build all bins at once instead of looping on the selections
		templateName = "{0}_{1}_SR_{2}".format(bkg,select,variable)
		template = inRoot.Get(templateName)
		if template.Integral()>0.000001 :
			processes.append(bkg)
			if bkg is not "QCD" :
                            MCbackgrounds.append(bkg)

	allQCD = False
	allQCDs = [0,0,0,0]
	for regionsuff in range(len(regionSuffix)) :
		for ichan in range(len(backgrounds)):
			if "QCD" in backgrounds[ichan] :
				fname = "data_obs"
				if regionSuffix[regionsuff] == "SR" :
					fname="QCD"
				templateName = "{0}_{1}_{3}_{2}".format(fname,select,variable,regionSuffix[regionsuff])
				template = inRoot.Get(templateName)
				#allQCDs.append(template.Integral())
				allQCDs[regionsuff]= allQCDs[regionsuff]+template.Integral()
				iQCD = ichan
			elif regionSuffix[regionsuff] is not "SR" :
				templateName = "{0}_{1}_{3}_{2}".format(backgrounds[ichan],select,variable,regionSuffix[regionsuff])
				template = inRoot.Get(templateName)
				allQCDs[regionsuff] = allQCDs[regionsuff] - template.Integral()

	if allQCDs[0]>0 and allQCDs[1]>0 and allQCDs[2]>0 and allQCDs[3]>0 : allQCD = True
	#for i in range(4) : print allQCDs[i]

        rates = []
        iQCD = -1
        totRate = 0
        templateName = "data_obs_{0}_{2}_{1}".format(select,variable,regionSuffix[region])
        template = inRoot.Get(templateName)
        obs = template.GetEntries()

        for proc in range(len(backgrounds)):
            if "QCD" in backgrounds[proc] :
                rates.append(-1)
                iQCD = proc
            else :
                templateName = "{0}_{1}_{3}_{2}".format(backgrounds[proc],select,variable,regionSuffix[region])
                template = inRoot.Get(templateName)

                brate = template.Integral()
                rates.append(brate)
                totRate = totRate + brate
        if iQCD >= 0 : rates[iQCD] = TMath.Max(0.0000001,obs-totRate)

        for proc in range(len(signals)):
            templateName = "{0}_{1}_{3}_{2}".format(signals[proc],select,variable,regionSuffix[region])
            template = inRoot.Get(templateName)
            srate = template.Integral()
            rates.append(srate)

        if region == 0 :
            syst = systReader("../config/systematics.cfg",signals,backgrounds,None)
            syst.writeOutput(False)
            syst.verbose(True)
            if(opt.channel == "TauTau" ): 
                syst.addSystFile("../config/systematics_tautau.cfg")
            elif(opt.channel == "MuTau" ): 
                syst.addSystFile("../config/systematics_mutau.cfg")
            elif(opt.channel == "ETau" ): 
                syst.addSystFile("../config/systematics_etau.cfg")
            if opt.theory : syst.addSystFile("../config/syst_th.cfg")
            syst.writeSystematics()
            proc_syst = {} # key = proc name; value = {systName: [systType, systVal]] } # too nested? \_(``)_/
            for proc in backgrounds:   proc_syst[proc] = {}
            for proc in signals:       proc_syst[proc] = {}

            systsShape  = ["CMS_scale_t_13TeV_DM0"] # <-- ADD HERE THE OTHER TES/JES SYST SHAPES (TOP SYST SHAPE IS ADDED BY HAND LATER)
            systsNorm   = []                        # <-- THIS WILL BE FILLED FROM CONFIGS

            for isy in range(len(syst.SystNames)) :
                if "CMS_scale_t" in syst.SystNames[isy] or "CMS_scale_j" in syst.SystNames[isy]: continue
                for iproc in range(len(syst.SystProcesses[isy])) :
                    if "/" in syst.SystValues[isy][iproc] :
                        f = syst.SystValues[isy][iproc].split("/")
                        systVal = (float(f[0]),float(f[1]))
                    else :
                        systVal = float(syst.SystValues[isy][iproc])
                        print "adding Syst",systVal,syst.SystNames[isy],syst.SystTypes[isy],"to",syst.SystProcesses[isy][iproc]                        
                        proc_syst[syst.SystProcesses[isy][iproc]][syst.SystNames[isy]] = [syst.SystTypes[isy], systVal]
                        systsNorm.append(syst.SystNames[isy])

            if opt.shapeUnc > 0:
                for name in systsShape:
                    for proc in MCbackgrounds: proc_syst[proc][name] = ["shape", 1.]   #applying jes or tes to all MC backgrounds
                    for proc in signals:       proc_syst[proc][name] = ["shape", 1.]   #applying jes or tes to all signals 
                #proc_syst["TT"]["top"] = ["shape", 1] ### NEED TO UNCOMMENT THESE TWO LINES  
                #systsShape.append("top")              ### WHEN TOP BKGS ARE IN

            col1 = '{: <40}'
            colsysN = '{: <30}'
            colsysType = '{: <10}'
            cols = '{: >25}'
            ratecols = '{0: > 25.4f}'
        	
            shapes_lines_toWrite = []
            lnN_lines_toWrite     = []
        	
            for name in systsShape:
                shapes_lines_toWrite.append(colsysN.format(name))
                shapes_lines_toWrite.append(colsysType.format("shape"))
                for lineproc in backgrounds: shapes_lines_toWrite.append(cols.format("1" if name in proc_syst[lineproc].keys() else "-"))
                for lineproc in signals:     shapes_lines_toWrite.append(cols.format("1" if name in proc_syst[lineproc].keys() else "-"))
                shapes_lines_toWrite.append("\n")

            for name in systsNorm:
                lnN_lines_toWrite.append(colsysN.format(name))
                lnN_lines_toWrite.append(colsysType.format("lnN"))
                for lineproc in backgrounds: lnN_lines_toWrite.append(cols.format("1" if name in proc_syst[lineproc].keys() else "-"))
                for lineproc in signals:     lnN_lines_toWrite.append(cols.format("1" if name in proc_syst[lineproc].keys() else "-"))
                lnN_lines_toWrite.append("\n")

            ########################
            
            outFile = "hh_{0}_C{1}_13TeV.txt".format(thechannel,theCat)
            
	    file = open(out_dir+outFile, "wb")
            
	    file.write    ('imax *  number of channels\n')
	    file.write    ('jmax *  number of processes minus 1\n')
	    file.write    ('kmax *  number of nuisance parameters\n')
	    file.write    ('----------------------------------------------------------------------------------------------------------------------------------\n')
	    ## shapes
	    
	    file.write    ('shapes * %s %s $PROCESS $PROCESS_$SYSTEMATIC\n'%(select, opt.filename))
	    file.write    ('----------------------------------------------------------------------------------------------------------------------------------\n')
	    
	    file.write    ((col1+cols+'\n').format('bin', select)) ### blind for now
	    ## observation
	    file.write    ((col1+cols+'\n').format('observation', '-1')) ### blind for now
	    
	    file.write    ('----------------------------------------------------------------------------------------------------------------------------------\n')
	    ## processes 
	    file.write    ('# list the expected events for signal and all backgrounds in that bin\n')
	    file.write    ('# the second process line must have a positive number for backgrounds, and 0 or neg for signal\n')
	    file.write    (col1.format('bin'))
	    for i in range(0,len(backgrounds)+len(signals)): 
	        file.write(cols.format(select))
	    file.write    ("\n")
	    file.write    (col1.format('process'))
	    for proc in backgrounds: 
	        file.write(cols.format(proc))
	    for proc in signals: 
	        file.write(cols.format(proc))
	    file.write    ("\n")
	    file.write    (col1.format("process"))
	    for i in range(1,len(backgrounds)+1): 
	        file.write(cols.format(i))
	    for i in range(0,len(signals)): 
	        file.write(cols.format(str(-int(i))))
	    file.write    ("\n")
	    file.write    (col1.format("rate"))
	    for proc in range(len(backgrounds)+len(signals)):
	        file.write(ratecols.format(rates[proc]))
	    file.write    ("\n")
	    file.write    ('----------------------------------------------------------------------------------------------------------------------------------\n')
            
            
            for line in shapes_lines_toWrite:
                file.write(line)
            for line in lnN_lines_toWrite:
                file.write(line)
            
            file.write    ('----------------------------------------------------------------------------------------------------------------------------------\n')            
            
                
            file.write    ('theory group = HH_BR_Hbb HH_BR_Htt QCDscale_ggHH pdf_ggHH\n')
                        
            file.write    ("alpha rateParam {0} QCD (@0*@1/@2) QCD_regB,QCD_regC,QCD_regD\n".format(select))
             
            if (opt.binbybin): file.write('\n* autoMCStats 10')
            
            file.close()

        else :
		outFile = "hh_{0}_C{1}_13TeV_{2}.txt".format(thechannel,theCat,regionName[region])

		file = open( out_dir+outFile, "wb")

		file.write("imax 1\n")
		file.write("jmax {0}\n".format(len(backgrounds)-1))
		file.write("kmax *\n")

		file.write("------------\n")
		file.write("shapes * * FAKE\n".format(opt.channel,regionName[region]))
		file.write("------------\n")

		templateName = "data_obs_{1}_{3}_{2}".format(bkg,select,variable,regionSuffix[region])
		template = inRoot.Get(templateName)        
		file.write("bin {0} \n".format(select))
		obs = template.GetEntries()
		file.write("observation {0} \n".format(obs))

		file.write("------------\n")

		file.write("bin ")        
		for chan in backgrounds:
			file.write("{0}\t ".format(select))
		file.write("\n")      

		file.write("process ")
		for chan in backgrounds:
			file.write("{0}\t ".format(chan))

		file.write("\n")

		file.write("process ")
		for chan in range(len(backgrounds)): #+1 for the QCD
			file.write("{0}\t ".format(chan+1))
		file.write("\n")

		file.write("rate ")
		rates = []
		iQCD = -1
		totRate = 0
		for ichan in range(len(backgrounds)):
			if "QCD" in backgrounds[ichan] :
				rates.append(-1)
				iQCD = ichan
			else :
				templateName = "{0}_{1}_{3}_{2}".format(backgrounds[ichan],select,variable,regionSuffix[region])
				template = inRoot.Get(templateName)
				brate = template.Integral()
				rates.append(brate)
				totRate = totRate + brate
		if iQCD >= 0 : rates[iQCD] = TMath.Max(0.0000001,obs-totRate)
		for ichan in range(len(backgrounds)):
			file.write("{0:.4f}\t".format(rates[ichan]))
		file.write("\n")
		file.write("------------\n")
		file.write("QCD_{0} rateParam  {1} QCD 1 \n".format(regionName[region],select))

        return (out_dir+outFile)

ROOT.gSystem.AddIncludePath("-I$ROOFITSYS/include/")
ROOT.gSystem.AddIncludePath("-Iinclude/")
ROOT.gSystem.Load("libRooFit")
ROOT.gSystem.Load("libHiggsAnalysisCombinedLimit.so")

parseOptions()
datacards = []
configname = opt.config
print configname
input = ConfigReader(configname)



if opt.overSel == "" :
	allSel = ["s1b1jresolvedMcut", "s2b0jresolvedMcut", "sboostedLLMcut", "VBFloose"]
else : allSel = [opt.overSel]

data     = input.readListOption("general::data")
signals     = input.readListOption("general::signals")
backgrounds = input.readListOption("general::backgrounds")

## replace what was merged
if input.hasSection("merge"):
    for groupname in input.config['merge']:
        mergelist = input.readListOption('merge::'+groupname)
        mergelistA = input.readOption('merge::'+groupname)
        theList = None
        if   mergelist[0] in data: theList = data
        elif mergelist[0] in signals:  theList = signals
        elif mergelist[0] in backgrounds:  theList = backgrounds
        for x in mergelist: theList.remove(x)
        theList.append(groupname)

backgrounds.append("QCD")

# rename signals following model convention
for i,sig in enumerate(signals):
        if "GGHH_NLO" in sig: signals[i] = sig.replace("GGHH_NLO","ggHH").replace("_xs","_kt_1_bbtt").replace("cHHH", "kl_")
        if "VBFHH"in sig:     signals[i] = sig.replace("VBFHH","qqHH").replace("C3","kl") #write 1_5 as 1p5 from the beginning

datacards = []

for sel in allSel : 
    for ireg in range(0,4) :
         card = writeCard(backgrounds,signals, sel,ireg)
         datacards.append(card)

if opt.makeworkspace:
    for card in datacards: os.system('text2workspace.py %s -P HHModel:HHdefault &'%card)
