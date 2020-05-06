PROG = grid-check

rpmsourcedir = /tmp/$(shell whoami)/rpmbuild

# The rules

rpm:	
	mkdir -p $(rpmsourcedir) ; \
        if [ -a $(PROG).spec ]; \
        then \
          tar -C ../ --exclude .svn \
                   -cf $(rpmsourcedir)/$(PROG).tar $(PROG) ; \
          gzip -f $(rpmsourcedir)/$(PROG).tar ; \
          rpmbuild -ta $(rpmsourcedir)/$(PROG).tar.gz ; \
          rm -f $(rpmsourcedir)/$(LIB).tar.gz ; \
        else \
          echo $(rpmerr); \
        fi;
