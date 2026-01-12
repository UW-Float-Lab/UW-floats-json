.DEFAULT:
.SUFFIXES:
.PHONY: all clean force Limits Clean-Limits Trajectory Clean-Trajectory \
        Index-Html Clean-Index-Html XY-Plots Clean-XY-Plots \
        Hammer-Plot Clean-Hammer-Plot Mercator-Plot Clean-Mercator-Plot \
        TP-Plots Clean-TP-Plots Html Clean-Html TP-Html Clean-TP-Html \
        XY-Html Clean-XY-Html

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# $Id$
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# RCS Log:
#
# $Log$
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# define the shell to use
SHELL=/bin/tcsh

# location of the root directory
Root = /www/argo#

# location of bin directory
Bin = $(Root)/bin#

# location of the data directory
Data = $(Root)/data#

# get the float id from the current directory
FloatId := $(notdir $(shell pwd))

# define the globbing pattern for the floats
FloatGlob = $(Data)/[0-9][0-9][0-9]*[0-9]

# define the globbing pattern for the profiles 
ProfileGlob = $(FloatId).[0-9][0-9][0-9].msg

# build a list of all floats to consider
Floats := $(patsubst $(Data)/%,%,$(sort $(wildcard $(FloatGlob))))

# build a list of all profiles to consider
Profiles := $(patsubst %.msg,%.edf,$(sort $(wildcard $(ProfileGlob))))

# make a list of intermediate files that shouldn't be deleted
.PRECIOUS: %.edf %.jpeg %.ps $(Root)/homographs/TP/$(FloatId)/%.ps

#========================================================================
# General section to manage the maintenance of all plots & renderings
#=======================================================================

$(FloatId): Limits Trajectory XY-Plots TP-Plots TS-Plot Engineering-Plots \
      Html PresentStatus
	@echo Done make $@ ...

clean: Clean-Html Clean-XY-Plots Clean-TP-Plots Clean-TS-Plot Clean-Limits \
       Clean-Trajectory Clean-Engineering-Plots Clean-PresentStatus
	@echo Done making $@ ...

#========================================================================
# Section to manage engineering plots
#========================================================================

Engineering-Plots: Battery-Plot Piston-Plot Pump-Time-Plot Amps-Plot \
      Surface-Pressure-Plot Humidity-Plot Vacuum-Plot Coulomb-Plot
	@echo Done making $@ ...

Clean-Engineering-Plots: Clean-Battery-Plot Clean-Piston-Plot \
      Clean-Pump-Time-Plot Clean-Amps-Plot Clean-Surface-Pressure-Plot \
      Clean-Humidity-Plot Clean-Vacuum-Plot Clean-Coulomb-Plot
	@echo Done making $@ ...

Battery-Plot: $(Root)/engineering/$(FloatId)/bat-time-series.jpeg
	@echo Done making $@ ...

Clean-Battery-Plot: force
	-rm -f $(Root)/engineering/$(FloatId)/bat-time-series.{jpeg,ps}

$(Root)/engineering/$(FloatId)/bat-time-series.ps: $(Profiles)
	$(Bin)/bat-time-series-Ir061125.gmt $(FloatId)

Piston-Plot: $(Root)/engineering/$(FloatId)/piston-position.jpeg
	@echo Done making $@ ...

Clean-Piston-Plot: force
	-rm -f $(Root)/engineering/$(FloatId)/piston-position.{jpeg,ps}

$(Root)/engineering/$(FloatId)/piston-position.ps: $(Profiles)
	$(Bin)/piston-position-pnp.gmt  $(FloatId)

Pump-Time-Plot:  $(Root)/engineering/$(FloatId)/pump-motor-time.jpeg
	@echo Done making $@ ...

Clean-Pump-Time-Plot: force
	-rm -f $(Root)/engineering/$(FloatId)/pump-motor-time.{jpeg,ps}

$(Root)/engineering/$(FloatId)/pump-motor-time.ps: $(Profiles)
	$(Bin)/pump-motor-time.gmt  $(FloatId)

Amps-Plot:  $(Root)/engineering/$(FloatId)/amps-time-series.jpeg
	@echo Done making $@ ...

Clean-Amps-Plot: force
	-rm -f $(Root)/engineering/$(FloatId)/amps-time-series.{jpeg,ps}

$(Root)/engineering/$(FloatId)/amps-time-series.ps: $(Profiles)
	$(Bin)/amps-time-series-Ir061125.gmt  $(FloatId)

Surface-Pressure-Plot: $(Root)/engineering/$(FloatId)/surface-pressure.jpeg
	@echo Done making $@ ...

Clean-Surface-Pressure-Plot: force
	-rm -f $(Root)/engineering/$(FloatId)/surface-pressure.{jpeg,ps}

$(Root)/engineering/$(FloatId)/surface-pressure.ps: $(Profiles)
	$(Bin)/surface-pressure.gmt  $(FloatId)

Humidity-Plot: $(Root)/engineering/$(FloatId)/humidity.jpeg
	@echo Done making $@ ...

Clean-Humidity-Plot: force
	-rm -f $(Root)/engineering/$(FloatId)/humidity.{jpeg,ps}

$(Root)/engineering/$(FloatId)/humidity.ps: $(Profiles)
	$(Bin)/humidity.gmt  $(FloatId)

Vacuum-Plot: $(Root)/engineering/$(FloatId)/vacuum.jpeg
	@echo Done making $@ ...

Clean-Vacuum-Plot: force
	-rm -f $(Root)/engineering/$(FloatId)/vacuum.{jpeg,ps}

$(Root)/engineering/$(FloatId)/vacuum.ps: $(Profiles)
	$(Bin)/vacuum.gmt  $(FloatId)

Coulomb-Plot: $(Root)/engineering/$(FloatId)/apf11-coulomb.jpeg
	@echo Done making $@ ...

Clean-Coulomb-Plot: force
	-rm -f $(Root)/engineering/$(FloatId)/apf11-coulomb.{jpeg,ps}

$(Root)/engineering/$(FloatId)/apf11-coulomb.ps: $(Profiles)
	$(Bin)/apf11-coulomb.gmt  $(FloatId)

#========================================================================
# Section to manage generation of enginering html files
#========================================================================

Engineering-Html: $(Root)/engineering/$(FloatId)/index.shtml
	@echo Done making $@ ...

Clean-Engineering-Html: force
	-rm -f $(Root)/engineering/$(FloatId)/index.shtml

$(Root)/engineering/$(FloatId)/index.shtml: $(Profiles) \
   $(Root)/engineering/$(FloatId)/comment.html \
   $(Data)/$(FloatId)/comment.html
	$(Bin)/engineering-html id=$(FloatId) $(Floats)
	-chmod +x $@

$(Root)/engineering/$(FloatId)/comment.html:
	-@touch $@

$(Data)/$(FloatId)/comment.html:
	-@touch $@

#========================================================================
# Section to manage Hammer-Plot homographs
#========================================================================

# target to make trajectory maps on a large scale map (for context)
Hammer-Plot: $(Root)/homographs/XY/$(FloatId)-hammer.jpeg
	@echo Done making $@ ...

# target to remove Hammer-Plot plot & jpeg file
Clean-Hammer-Plot:
	-rm -f $(Root)/homographs/XY/$(FloatId)-hammer.{ps,jpeg}

# target to execute the gmt script that creates a Hammer-Plot XY homograph
$(Root)/homographs/XY/$(FloatId)-hammer.ps: $(Profiles) lat.limits lon.limits
	-$(Bin)/Hammer.gmt $(FloatId)

#========================================================================
# Section to manage generation of html files
#========================================================================

# target to manage generation of html files
Html: Index-Html TP-Html XY-Html Engineering-Html
	@echo Done making $@ ...

# target to remove all html files
Clean-Html: Clean-Index-Html Clean-TP-Html Clean-XY-Html Clean-Engineering-Html
	@echo Done making $@ ...

#========================================================================
# Section to manage generation of indexes
#========================================================================

# target to manage generation of html index files
Index-Html: $(Root)/homographs/index/index.shtml $(Root)/homographs/index/$(FloatId).shtml
	@echo Done making $@ ...

# target to remove index html files
Clean-Index-Html: 
	-rm -f $(Root)/homographs/index/{index.shtml,$(FloatId).shtml}

# target to create index directory html file
$(Root)/homographs/index/index.shtml: $(Profiles)
	-$(Bin)/Index of=$@ $(Floats)

# target to create index html file for a single float
$(Root)/homographs/index/$(FloatId).shtml: $(Profiles) \
    $(Root)/homographs/index/$(FloatId)-comment.html
	-$(Bin)/indexhtml id=$(FloatId) r=$(Data) of=$@
	-@chmod +x $@

$(Root)/homographs/index/$(FloatId)-comment.html:
	-@touch $@

#========================================================================
# Section to manage the collection of extremes for all floats/profiles
#========================================================================

# target to skulk the extremes of variables over the suite of floats & profiles
Limits: $(patsubst %.edf,%.cnt,$(Profiles))
	@echo Done making $@ ...

# target to remove data file summaries & limit files
Clean-Limits:
	-rm -f [0-9][0-9][0-9][0-9].[0-9][0-9][0-9].cnt *.limits

# target to execute the limit-skulker for a single file
%.cnt: %.edf
	-edfcount if=$< of=$@; $(Bin)/limits $@;

# convert argos messages to an EDF data file
%.edf: %.msg
	-$(Bin)/Apf11Sbe41cpOptodeIsusPhFlbbOcr061125-parser if=$< of=$@

#========================================================================
# Section to manage data for the rollcall generator
#========================================================================

PresentStatus: $(Profiles)
	-$(Bin)/present-status model=Apf11Sbe41cpOptodeIsusPhFlbbOcr r=$(Data) id=$(FloatId) 

Clean-PresentStatus: 
	-rm -f present-status.out

#========================================================================
# Section to manage Mercator homographs
#========================================================================

# target to make Mercator close-ups of profiles along trajectory
Mercator-Plot: $(Root)/homographs/XY/$(FloatId)-mercator.jpeg
	@echo Done making $@ ...

# target to remove Mercator plot & jpeg file
Clean-Mercator-Plot:
	-rm -f $(Root)/homographs/XY/$(FloatId)-mercator.{ps,jpeg}

# target to execute the gmt script that creates a Mercator XY homograph
$(Root)/homographs/XY/$(FloatId)-mercator.ps: $(Profiles) lat.limits lon.limits
	-$(Bin)/Mercator.gmt $(FloatId)

#========================================================================
# Section to manage generation of TP-html files
#========================================================================

# target to manage generation of TP html files
TP-Html: $(patsubst %.edf,$(Root)/homographs/TP/$(FloatId)/%.shtml,$(Profiles)) \
         $(Root)/homographs/TP/TP.shtml
	@echo Done making $@ ...

# target to remove TP html files
Clean-TP-Html:
	-rm -f $(Root)/homographs/TP/{TP,$(FloatId){,/$(FloatId).[0-9][0-9][0-9]}}.shtml

# create TP directory file
$(Root)/homographs/TP/TP.shtml: $(Profiles)
	-$(Bin)/TP of=$(Root)/homographs/TP/TP.shtml $(Floats)

# create html file for a single TSP plot
$(Root)/homographs/TP/$(FloatId)/%.shtml: $(Data)/$(FloatId)/%.edf \
    $(Root)/homographs/TP/$(FloatId)/comment.html 
	-$(Bin)/tsphtml id=$(FloatId)
	-@chmod +x $@ $(Root)/homographs/TP/$(FloatId).shtml

$(Root)/homographs/TP/$(FloatId)/comment.html:
	-@touch $@

#========================================================================
# Section to manage TP homographs
#========================================================================

# target to create TP homographs
TP-Plots: $(patsubst %.edf,$(Root)/homographs/TP/$(FloatId)/%.jpeg,$(Profiles))
	@echo Done making $@ ...

# target to remove TP homographs
Clean-TP-Plots: force
	-rm -f $(Root)/homographs/TP/$(FloatId)/$(FloatId).[0-9][0-9][0-9].{jpeg,ps}

# target to execute the gmt script that creates a given TP homograph
$(Root)/homographs/TP/$(FloatId)/%.ps: $(Data)/$(FloatId)/%.edf $(Data)/p.limits \
                                       $(Data)/s.limits $(Data)/t.limits
	-$(Bin)/TspIsusPhFlbbOcr-Ir.gmt $(subst ., ,$(*F))

#========================================================================
# Section to manage TS homographs
#========================================================================

# target to create TS homograph
TS-Plot: $(Root)/homographs/TP/$(FloatId)/$(FloatId).ts.jpeg
	@echo Done making $@ ...

# target to remove TS homographs
Clean-TS-Plot: force
	-rm -f $(Root)/homographs/TP/$(FloatId)/$(FloatId).ts.{jpeg,ps}

# target to execute the gmt script that creates a given TS homograph
$(Root)/homographs/TP/$(FloatId)/$(FloatId).ts.ps: \
        $(Data)/$(FloatId)/$(FloatId).[0-9][0-9][0-9].edf \
        $(Data)/$(FloatId)/s.limits $(Data)/$(FloatId)/t.limits
	-$(Bin)/TsIsusPhFlbb-Ir.gmt $(FloatId)

#========================================================================
# Section to manage generation of trajectories
#========================================================================

# target to manage generation of trajectory file
Trajectory: trajectory
	@echo Done make $@ ...

# target to remove trajectory file
Clean-Trajectory: 
	-rm -f trajectory

# target to make a file containing trajectory info
trajectory: $(Profiles)
	-$(Bin)/xy of=$@ $(Profiles)

#========================================================================
# Section to manage generation of XY-html files
#========================================================================

# target to manage generation of XY html files
XY-Html: $(Root)/homographs/XY/$(FloatId).shtml $(Root)/homographs/XY/XY.shtml
	@echo Done making $@ ...

# target to remove XY html files
Clean-XY-Html:
	-rm -f $(Root)/homographs/XY/{XY,$(FloatId)}.shtml

# create XY directory html file
$(Root)/homographs/XY/XY.shtml: $(Profiles)
	-$(Bin)/XY of=$(Root)/homographs/XY/XY.shtml $(Floats)

# create html file for a single float
$(Root)/homographs/XY/$(FloatId).shtml: $(Profiles) \
    $(Root)/homographs/XY/$(FloatId)-comment.html
	-$(Bin)/xyhtml id=$(FloatId)
	-@chmod +x $@

$(Root)/homographs/XY/$(FloatId)-comment.html:
	-@touch $@

#========================================================================
# Section to manage XY homographs
#========================================================================

# target to create XY homographs
XY-Plots: Mercator-Plot Hammer-Plot
	@echo Done making $@ ...

# target to remove XY homographs
Clean-XY-Plots: Clean-Hammer-Plot Clean-Mercator-Plot
	@echo Done making $@ ...

#========================================================================
# Section of shared targets
#========================================================================

# target to convert from postscript format to jpeg format
%.jpeg: %.ps
	-convert -density 72 -geometry 100% $< $@ >& /dev/null

lat.limits lon.limits p.limits t.limits: Limits
