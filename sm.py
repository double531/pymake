#!/usr/bin/env python3

# Parse GNU Make with state machine. 
# Trying hand crafted state machines over pyparsing. GNU Make has very strange
# rules around whitespace.
#
# davep 09-sep-2014

import sys

# require Python 3.x for best Unicode handling
if sys.version_info.major < 3:
    raise Exception("Requires Python 3.x")

whitespace = set( ' \t\r\n' )

class ParseError(Exception):
    pass

# tinkering with a class for tokens
#def Token(s): return s

class Token(object):
    def __init__(self,s):
        self.string = s

    def __str__(self):
        return self.string

    def __repr__(self):
        return self.string

def comment(string):
    state_start = 1
    state_eat_comment = 2
    state_escape = 3

    state = state_start
    for c in string : 
#        print("c={0} state={1}".format(c,state))
        if state==state_start:
            if c=='#':
                state = state_eat_comment
            elif c=='\\':
                yield c
                state = state_escape
            else:
                yield c
        elif state==state_eat_comment:
            if c=='\n' :
                yield c
                state = state_start
            # otherwise char is eaten
        elif state==state_escape:
            yield c
            state = state_start
        else:
            assert 0, state

def eatwhite(string):
    # eat all whitespace (testing characters + sets)
    for c in string:
        if not c in whitespace:
            yield c

def parse_variable_ref(string):
    
    state_start = 1
    state_dollar = 2
    state_parsing = 3

    state = state_start
    token = ""

#    print( "state={0}".format(state))

    for c in string : 
#        print("c={0} state={1}".format(c,state))
        if state==state_start:
            if c=='$':
                state=state_dollar
        elif state==state_dollar:
            # looking for '(' or '$' or some char
            if c=='(' or c=='{':
                opener = c
                state = state_parsing
                yield Token("$"+c)
            elif c=='$':
                # literal "$$"
                yield Token("$$")
                return 
            elif not c in whitespace :
                # single letter variable, e.g., $@ $x $_ etc.
                token += c
                yield Token("$")
                yield Token(token)
                return 
        elif state==state_parsing:
            if c==')' or c=='}':
                # TODO make sure to match the open/close chars
                yield Token(token)
                yield Token(c)
                return 
            elif c=='$':
                # nested expression!  :-O
                # if lone $$ token, preserve the $$ in the current token string
                # otherwise, recurse into parsing a $() expression
                if string.lookahead()=='$':
                    token += "$$"
                    string.next()
                else:
                    # return token so far
                    yield Token(token)
                    # restart token
                    token = ""
                    # push the '$' back onto the scanner
                    string.pushback()
                    # recurse into this scanner again
                    for t in parse_variable_ref(string):
                        yield t
                    # python 3.3 and above
                    #yield from parse_variable_ref(string)
            else:
                token += c

    raise ParseError()

class ScannerIterator(object):
    # string iterator that allows look ahead and push back
    def __init__(self,string):
        self.string = string
        self.idx = 0
        self.max_idx = len(self.string)

    def __iter__(self):
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        if self.idx >= self.max_idx:
            raise StopIteration
        self.idx += 1
        return self.string[self.idx-1]

    def lookahead(self):
        if self.idx >= self.max_idx:
            raise StopIteration
#        print("lookahead={0}".format(self.string[self.idx]))
        return self.string[self.idx]

    def pushback(self):
        if self.idx <= 0 :
            raise StopIteration
        self.idx -= 1

def parse(infilename):
    infile = open(infilename)
    all_lines = infile.readlines()
    infile.close()

    s = "".join(all_lines)
    
    my_iter = ScannerIterator(s)

    new_makefile = "".join( [ c for c in eatwhite(comment(my_iter)) ] )
    print(new_makefile)

#    for c in comment(s):
#        print(c,end="")


def expression_test():

    expression_tests = ( 
        # string    result
        ("$$",      ("$$",)),
        ("$$$$$$",      ("$$$$$$",)),
        ("$(CC)",   ("$(","CC",")")),
        ("$( CC )", ("$("," CC ", ")")),
        ("$(CC$$)",   ("$(","CC$$", ")")),
        ("$(CC$(LD))",   ("$(","CC","$(","LD",")","",")")),
        ("${CC}",   ("${","CC","}")),
        ("$@",      ("$", "@",)),
        ("$<",      ("$", "<",)),
        ("$F",      ("$","F",)),
        ("$Ff",      ("$","F","f",)),
        ("$F$f",      ("$","F","$","f",)),
        ("$$$F$f",      ("$$","$","F","$","f",)),
        ("$($($(FOO)))",    ("$(","","$(","","$(","FOO",")","",")","",")")),
        ("$($($(FOO)a)b)c", ("$(","","$(","","$(","FOO",")","a",")","b",")")),
        ("$(a$(b$(FOO)a)b)c", ("$(","a","$(","b","$(","FOO",")","a",")","b",")")),
        ("$($($F)))",       ("$(","","$(","","$","F","",")","",")","",")")),
        ("$($($Fqq)))",     ("$(","","$(","","$","F","qq",")","",")","",")")),
        ("$(foo   )",       ("$(","foo   ",")")),
        ("$(info this is an info message)",     ("$(","info this is an info message",")")),
        ("$(error this is an error message)",   ("$(","error this is an error message",")")),
        ("$(findstring a,a b c)",               ("$(","findstring a,a b c",")")),
        ("$(patsubst %.c,%.o,x.c.c bar.c)",     ("$(","patsubst %.c,%.o,x.c.c bar.c",")")),
        ("$(filter %.c %.s,$(sources))",        ("$(",
                                                    "filter %.c %.s,",
                                                    "$(",
                                                    "sources",
                                                    ")",
                                                    "",
                                                    ")",
                                                )),
        ("$(objects:.o=.c)",        ("$(","objects:.o=.c",")",)),
        ("$(filter-out $(mains),$(objects))",   ("$(","filter-out ","$(","mains",")",",","$(","objects",")","",")","",")")),
        ("$(subst :, ,$(VPATH))",   ("$(","subst :, ,","$(","VPATH",")","",")")), # spaces are significant!
#        ("$(foo)$(\#)bar=thisisanother\#testtesttest", ("$(","k
        ("$(info = # foo#foo foo#foo foo#foo ###=# foo#foo foo#foo foo#foo ###)",
          ("$(","info = # foo#foo foo#foo foo#foo ###=# foo#foo foo#foo foo#foo ###",")")),
    )
    for test in expression_tests :
        print("test={0}".format(test))
        s,result = test
        print("s={0}".format(s))
        my_iter = ScannerIterator(s)
        tokens = [ t for t in parse_variable_ref(my_iter)] 
        print( "tokens={0}".format("||".join([t.string for t in tokens])) )

        for v in zip(tokens,result):
#            assert  v[0]==v[1], v
            assert  v[0].string==v[1], v

    # this should fail
#    print( "var={0}".format(parse_variable_ref(ScannerIterator("$(CC"))) )

def test():
    expression_test()

def main():
    import sys
    for infilename in sys.argv[1:]:
        parse(infilename)
    test()

if __name__=='__main__':
    main()

