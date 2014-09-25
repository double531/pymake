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

#whitespace = set( ' \t\r\n' )
whitespace = set( ' \t' )

assignment_operators = {"=","?=",":=","::=","+=","!="}
rule_operators = { ":", "::" }
eol = set("\r\n")

recipe_prefix = "\t"

# 4.8 Special Built-In Target Names
built_in_targets = {
        ".PHONY",
        ".SUFFIXES",
        ".DEFAULT",
        ".PRECIOUS",
        ".INTERMEDIATE",
        ".SECONDARY",
        ".SECONDEXPANSION",
        ".DELETE_ON_ERROR",
        ".IGNORE",
        ".LOW_RESOLUTION_TIME",
        ".SILENT",
        ".EXPORT_ALL_VARIABLES",
        ".NOTPARALLEL",
        ".ONESHELL",
        ".POSIX",
    }

# Stuff from Appendix A.
directive = { 
              "define", "enddef", "undefine",
              "ifdef", "ifndef", "else", "endif", 
              "include", "-include", "sinclude",
              "override", "export", "unexport",
              "private",
              "vpath", 
            }
functions = { 
                "subst",
                "patsubst",
                "strip",
                "findstring",
                "filter",
                "filter-out",
                "sort",
                "word",
                "words",
                "wordlist",
                "firstword",
                "lastword",
                "dir",
                "notdir",
                "suffix",
                "basename",
                "addsuffix",
                "addprefix",
                "join",
                "wildcard",
                "realpath",
                "absname",
                "error",
                "warning",
                "shell",
                "origin",
                "flavor",
                "foreach",
                "if",
                "or",
                "and",
                "call",
                "eval",
                "file",
                "value",
            }
automatic_variables = {
                "@",
                "%",
                "<",
                "?",
                "^",
                "+",
                "*",
                "@D",
                "@F",
                "*D",
                "*F",
                "%D",
                "%F",
                "<D",
                "<F",
                "^D",
                "^F",
                "+D",
                "+F",
                "?D",
                "?F",
            }
builtin_variables = {
                "MAKEFILES",
                "VPATH",
                "SHELL",
                "MAKESHELL",
                "MAKE",
                "MAKE_VERSION",
                "MAKE_HOST",
                "MAKELEVEL",
                "MAKEFLAGS",
                "GNUMAKEFLAGS",
                "MAKECMDGOALS",
                "CURDIR",
                "SUFFIXES",
                ".LIBPATTEREN",
            }

class ParseError(Exception):
    pass

class NestedTooDeep(Exception):
    pass

#
#  Class Hierarchy for Tokens
#
class Symbol(object):
    # base class of everything we find in the makefile
    def __init__(self,string):
        # by default, save the token's string 
        # (descendent classes could store something differnet)
        self.string = string

    def __str__(self):
        # create a string such as "Literal(all)"
        # TODO handle embedded " and ' (with backslashes I guess?)
        return "{0}(\"{1}\")".format(self.__class__.__name__,self.string)
#        return "{0}({1})".format(self.__class__.__name__,self.string)

    def __eq__(self,rhs):
        # lhs is self
        return self.string==rhs.string

    def makefile(self):
        # create a Makefile from this object
        return self.string

class Literal(Symbol):
    # A literal found in the token stream. Store as a string.
    pass

class Operator(Symbol):
    pass

class AssignOp(Operator):
    # An assignment symbol, one of { = , := , ?= , += , != , ::= }
    pass
    
class RuleOp(Operator):
    # A rule sumbol, one of { : , :: }
    pass
    
class Expression(Symbol):
    # An expression is a list of symbols.
    def __init__(self, token_list ):
        self.token_list = token_list

        # sanity check
        for t in self.token_list :
#            print("t={0}".format( t ) )
            assert isinstance(t,Symbol), (type(t),t)

    def __str__(self):
        # return a ()'d list of our tokens
        s = "{0}( [".format(self.__class__.__name__)
        if 0:
            for t in self.token_list :
                s += str(t)
        else:
            s += ",".join( [ str(t) for t in self.token_list ] )
        s += "])"
        return s

    def __getitem__(self,idx):
        return self.token_list[idx]

    def __eq__(self,rhs):
        # lhs is self
        # rhs better be another expression
        assert isinstance(rhs,Expression),(type(rhs),rhs)

        if len(self.token_list) != len(rhs.token_list):
            return False

        for tokens in zip(self.token_list,rhs.token_list) :
            if tokens[0].__class__ != tokens[1].__class__ : 
                return False

            # Recurse into sub-expressions. It's tokens all the way down!
            if not tokens[0] == tokens[1] :
                return False

        return True

    def makefile(self):
        # Build a Makefile string from this rule expression.
        s = ""
        for t in self.token_list : 
            s += t.makefile()
        return s
            

class VarRef(Expression):
    # A variable reference found in the token stream. Save as a nested set of
    # tuples representing a tree. 
    # $a            ->  VarExp(a)
    # $(abc)        ->  VarExp(abc,)
    # $(abc$(def))  ->  VarExp(abc,VarExp(def),)
    # $(abc$(def)$(ghi))  ->  VarExp(abc,VarExp(def),)
    # $(abc$(def)$(ghi))  ->  VarExp(abc,VarExp(def),VarExp(ghi),)
    # $(abc$(def)$(ghi$(jkl)))  ->  VarExp(abc,VarExp(def),VarExp(ghi,VarExp(jkl)),)
    # $(abc$(def)xyz)           ->  VarExp(abc,VarRef(def),Literal(xyz),)
    # $(info this is a varref)  ->  VarExp(info this is a varref)

    def makefile(self):
        s = "$("
        for t in self.token_list : 
            s += t.makefile()

        s += ")"
        return s

class AssignmentExpression(Expression):
    def __init__(self,token_list):
        Expression.__init__(self,token_list)

        # AssignmentExpression :=  Expression AssignOp Expression
        assert len(self.token_list)==3,len(self.token_list)
        assert isinstance(self.token_list[0],Expression)
        assert isinstance(self.token_list[1],AssignOp)
        assert isinstance(self.token_list[2],Expression),(type(self.token_list[2]),)

class RuleExpression(Expression):
    pass

class PrerequisiteList(Expression):
    def makefile(self):
        # space separated
        s = " ".join( [ t.makefile() for t in self.token_list ] )
        return s

class Recipe(Expression):
    # A single line of a recipe
    pass

class RecipeList( Expression ) : 
    # A collection of recipes

    def makefile(self):
        # newline separated
        s = "\t"+"\n\t".join( [ t.makefile() for t in self.token_list ] )
        return s

def comment(string):
    state_start = 1
    state_eat_comment = 2

    state = state_start

    # this could definitely be faster (method in ScannerIterator to eat until EOL?)
    for c in string : 
#        print("c={0} state={1}".format(c,state))
        if state==state_start:
            if c=='#':
                state = state_eat_comment
            else:
                # shouldn't be here unless comment
                raise ParseError()
        elif state==state_eat_comment:
            # comments finish at end of line
            # FIXME handle \r\n,\n\r,\r and other weird line endings
            if c=='\n' :
                return
            # otherwise char is eaten
        else:
            assert 0, state

def eatwhite(string):
    # eat all whitespace (testing characters + sets)
    for c in string:
        if not c in whitespace:
            yield c

depth = 0
def depth_reset():
    # reset the depth (used when testing the depth checker)
    global depth
    depth = 0

def depth_checker(func):
    # Avoid very deep recurssion into tokenizers.
    # Note this uses a global so is NOT thread safe.
    def check_depth(*args):
        global depth
        depth += 1
        if depth > 10 : 
            raise NestedTooDeep(depth)
        ret = func(*args)
        depth -= 1

        # shouldn't happen!
        assert depth >= 0, depth 

        return ret

    return check_depth

@depth_checker
def tokenize_assignment_or_rule(string):
    # at start of scanning, we don't know if this is a rule or an assignment
    # this is a test : foo   -> (this,is,a,test,:,)
    # this is a test = foo   -> (this is a test,=,)
    #
    # I tokenize assuming it's an assignment statement. If the final token is a
    # rule token, then I re-tokenize as a rule.
    #

    # save current position in the token stream
    string.push_state()
    lhs = tokenize_statement_LHS(string)
    
    assert type(lhs)==type(())
    for token in lhs : 
        assert isinstance(token,Symbol),(type(token),token)

    statement_type = "rule" if lhs[-1].string in rule_operators else "assignment" 

    print( "last_token={0} ∴ statement is {1}".format(lhs[-1],statement_type))
    if lhs[-1].string in rule_operators :
        print("re-run as rule")
        string.pop_state()
        # re-tokenize as a rule (backtrack)
        lhs = tokenize_statement_LHS(string,whitespace)
    
        # add rule RHS
        statement = list(lhs)
        statement.append( tokenize_rule_prereq_or_assign(string) )

        return RuleExpression( statement ) 

    # The statement is an assignment. Tokenize rest of line as an assignment.
    statement = list(lhs)
    statement.append(tokenize_assign_RHS( string ))
    return AssignmentExpression( statement )

@depth_checker
def tokenize_statement_LHS(string,separators=""):
    # Tokenize the LHS of a rule or an assignment statement. A rule uses
    # whitespace as a separator. An assignment statement preserves internal
    # whitespace but leading/trailing whitespace is stripped.

    state_start = 1
    state_in_word = 2
    state_dollar = 3
    state_backslash = 4
    state_colon = 5
    state_colon_colon = 6

    state = state_start
    token = ""

    token_list = []

    # Before can disambiguate assignment vs rule, must parse forward enough to
    # find the operator. Otherwise, the LHS between assignment and rule are
    # identical.
    #
    # BNF is sorta
    # assignment ::= LHS assignment_operator RHS
    # rule       ::= LHS rule_operator RHS
    #

    # a \x of these chars replaced by literal x
    # XXX in both rule and assignment LHS? O_o
    backslashable = set("% :,")

    for c in string : 
#        print("r c={0} state={1} token=\"{2}\"".format(c,state,token))
        if state==state_start:
            # always eat whitespace while in the starting state
            if c in whitespace : 
                # eat whitespace
                pass
            elif c==':':
                state = state_colon
            else :
                # whatever it is, push it back so can tokenize it
                string.pushback()
                state = state_in_word

        elif state==state_in_word:
            if c=='\\':
                state = state_backslash

            # whitespace in LHS of assignment is significant
            # whitespace in LHS of rule is ignored
            elif c in separators :
                # end of word
                token_list.append( Literal(token) )

                # restart token
                token = ""

                # jump back to start searching for next symbol
                state = state_start

            elif c=='$':
                state = state_dollar

            elif c=='#':
                # eat the comment 
                string.pushback()
                comment(string)

            elif c==':':
                # end of LHS (don't know if rule or assignment yet)
                # strip trailing whitespace
                token_list.append( Literal(token.rstrip()) )
                state = state_colon

            elif c in set("?+!"):
                # maybe assignment ?= += !=
                # cheat and peekahead
                if string.lookahead()=='=':
                    string.next()
                    token_list.append(Literal(token.rstrip()))
                    return Expression(token_list),AssignOp(c+'=')
                else:
                    token += c

            elif c=='=':
                # definitely an assignment 
                # strip trailing whitespace
                token_list.append(Literal(token.rstrip()))
                return Expression(token_list),AssignOp("=")
                
            else :
                token += c

        elif state==state_dollar :
            if c=='$':
                # literal $
                token += "$"
            else:
                # save token so far; note no rstrip()!
                token_list.append(Literal(token))
                # restart token
                token = ""

                # jump to variable_ref tokenizer
                # restore "$" + "(" in the string
                string.pushback()
                string.pushback()

                # jump to var_ref tokenizer
                token_list.append( tokenize_variable_ref(string) )

            state=state_in_word

        elif state==state_backslash :
            if c in backslashable : 
                token += c
            else :
                # literal '\' + somechar
                token += '\\'
                token += c
            state = state_in_word

        elif state==state_colon :
            # assignment end of LHS is := or ::= 
            # rule's end of target(s) is either a single ':' or double colon '::'
            if c==':':
                # double colon
                state = state_colon_colon
            elif c=='=':
                # :=
                # end of RHS
                return Expression(token_list), AssignOp(":=") 
            else:
                # Single ':' followed by something. Whatever it was, put it back!
                string.pushback()
                # successfully found LHS 
                return Expression(token_list),RuleOp(":")

        elif state==state_colon_colon :
            # preceeding chars are "::"
            if c=='=':
                # ::= 
                return Expression(token_list), AssignOp("::=") 
            string.pushback()
            # successfully found LHS 
            return Expression(token_list), RuleOp("::") 

        else:
            assert 0,state

    # hit end of string; what was our final state?
    if state==state_colon:
        # ":"
        return Expression(token_list), RuleOp(":") 
    elif state==state_colon_colon:
        # "::"
        return Expression(token_list), RuleOp("::") 

    # don't raise error; just return assuming rest of string is happy 

@depth_checker
def tokenize_rule_prereq_or_assign(string):
    # We are on the RHS of a rule's : or ::
    # We may have a set of prerequisites
    # or we may have a target specific assignment.

    # save current position in the token stream
    string.push_state()
    rhs = tokenize_rule_RHS(string)

    # Not a prereq. We found ourselves an assignment statement.
    if rhs is None : 
        string.pop_state()

        # We have target-specifc assignment. For example:
        # foo : CC=intel-cc
        # retokenize as an assignment statement
        lhs = tokenize_statement_LHS(string)
        statement = list(lhs)

        assert lhs[-1].string in assignment_operators

        statement.append( tokenize_assign_RHS(string) )
        rhs = AssignmentExpression( statement )
    else : 
        assert isinstance(rhs,PrerequisiteList)

    # stupid human check
    for token in rhs : 
        assert isinstance(token,Symbol),(type(token),token)

    return rhs

@depth_checker
def tokenize_rule_RHS(string):

    # RHS ::=                       -->  empty perfectly valid
    #     ::= symbols               -->  simple rule's prerequisites
    #     ::= symbols : symbols     -->  implicit pattern rule
    #     ::= symbols | symbols     -->  order only prerequisite
    #     ::= assignment            -->  target specific assignment 
    #
    # RHS terminated by comment, EOL, ';'
    state_start = 1
    state_word = 2
    state_colon = 3
    state_double_colon = 4
    state_dollar = 5

    state = state_start
    token = ""
    token_list = []

    for c in string :
        print("p c={0} state={1} idx={2}".format(c,state,string.idx))

        if state==state_start :
            if c=='$':
                state = state_dollar
            elif c=='#':
                string.pushback()
                # eat comment until end of line
                comment(string)
                # bye!
                return PrerequisiteList(token_list)

            elif c==';':
                # end of prerequisites; start of recipe
                # note we don't preserve token because it will be empty at this
                # point
                # bye!
                return PrerequisiteList(token_list)
            elif not c in whitespace :
                string.pushback()
                state = state_word

        elif state==state_dollar :
            if c=='$':
                # literal $
                token += "$"
            else:
                # save token so far 
                token_list.append(Literal(token.rstrip()))
                # restart token
                token = ""

                # jump to variable_ref tokenizer
                # restore "$" + "(" in the string
                string.pushback()
                string.pushback()

                # jump to var_ref tokenizer
                token_list.append( tokenize_variable_ref(string) )

            state = state_word

        elif state==state_word:
            if c in whitespace :
                # save token so far 
                token_list.append(Literal(token.rstrip()))
                # restart the current token
                token = ""
                # restart eating whitespace
                state = state_start

            elif c=='\\':
                state = state_backspace

            elif c==':':
                state = state_colon
                # assignment? 
                # implicit pattern rule?

            elif c=='|':
                # We have hit token indicating order-only prerequisite.
                # TODO
                assert 0

            elif c in set("?+!"):
                # maybe assignment ?= += !=
                # cheat and peekahead
                if string.lookahead()=='=':
                    # definitely an assign; bail out and we'll retokenize as assign
                    return None
                else:
                    token += c

            elif c=='=':
                # definitely an assign; bail out and we'll retokenize as assign
                return None

            elif c=='#':
                string.pushback()
                # eat comment until end of line
                comment(string)
                # bye!
                token_list.append(Literal(token))
                return Expression(token_list)

            elif c=='$':
                state = state_dollar

            elif c==';':
                # end of prerequisites; start of recipe
                token_list.append(Literal(token))
                return PrerequisiteList(token_list)

            else:
                token += c
            

        elif state==state_colon : 
            if c==':':
                # maybe ::= 
                state = state_double_colon
            elif c=='=':
                # definitely an assign; bail out and we'll retokenize as assign
                return None
            else:
                # implicit pattern rule
                # TODO
                assert 0

        elif state==state_double_colon : 
            # found ::
            if c=='=':
                # definitely assign
                # bail out and retokenize as assign
                return None
            else:
                # is this an implicit pattern rule?
                # TODO
                assert 0

        else : 
            assert 0, state

    # save the token we've seen so far
    token_list.append(Literal(token))

    return PrerequisiteList(token_list)

@depth_checker
def tokenize_assign_RHS(string):

    state_start = 1
    state_dollar = 2
    state_literal = 3
    state_eol = 4

    state = state_start
    token = ""
    token_list = []

    for c in string :
#        print("a c={0} state={1} idx={2}".format(c,state,string.idx))
        if state==state_start :
            if c=='$':
                state = state_dollar
            elif c=='#':
                string.pushback()
                # eat comment until end of line
                comment(string)
                # bye!
                break
            elif not c in whitespace :
                string.pushback()
                state = state_literal

            # default will eat leading whitespace
            # once we leave the state state, we will never return
            # (all whitespace after leading whitespace is preserved)

        elif state==state_dollar :
            if c=='$':
                # literal $
                token += "$"
            else:
                # save token so far; note no rstrip()!
                token_list.append(Literal(token))
                # restart token
                token = ""

                # jump to variable_ref tokenizer
                # restore "$" + "(" in the string
                string.pushback()
                string.pushback()

                # jump to var_ref tokenizer
                token_list.append( tokenize_variable_ref(string) )

            state = state_literal

        elif state==state_literal:
            if c=='$' :
                state = state_dollar
            elif c=='#':
                string.pushback()
                # eat comment until end of line
                comment(string)
                # bye!
                token_list.append(Literal(token))
                return Expression(token_list)
            elif c in eol :
                state = state_eol
            else:
                token += c

        elif state==state_eol :
            if not c in eol :
                string.pushback()
                token_list.append(Literal(token))
                return Expression(token_list)

        else:
            assert 0, state

    # end of string
    # save what we've seen so far
    token_list.append(Literal(token))
    return Expression(token_list)

@depth_checker
def tokenize_variable_ref(string):
    # Tokenize a variable reference e.g., $(expression) or $c 
    # Handles nested expressions e.g., $( $(foo) )
    # Returns a VarExp object.

    state_start = 1
    state_dollar = 2
    state_in_var_ref = 3

    state = state_start
    token = ""
    token_list = []

    for c in string : 
#        print("v c={0} state={1} idx={2}".format(c,state,string.idx))
        if state==state_start:
            if c=='$':
                state=state_dollar
            else :
                raise ParseError()
        elif state==state_dollar:
            # looking for '(' or '$' or some char
            if c=='(' or c=='{':
                opener = c
                state = state_in_var_ref
            elif c=='$':
                # literal "$$"
                token += "$"
            elif not c in whitespace :
                # single letter variable, e.g., $@ $x $_ etc.
                token_list.append( Literal(c) )
                return VarRef(token_list)
                # done tokenizing the var ref

        elif state==state_in_var_ref:
            if c==')' or c=='}':
                # end of var ref
                # TODO make sure to match the open/close chars

                # save what we've read so far
                token_list.append( Literal(token) )
                return VarRef(token_list)
                # done tokenizing the var ref

            elif c=='$':
                # nested expression!  :-O
                # if lone $$ token, preserve the $$ in the current token string
                # otherwise, recurse into parsing a $() expression
                if string.lookahead()=='$':
                    token += "$"
                    string.next()
                else:
                    # save token so far
                    token_list.append( Literal(token) )
                    # restart token
                    token = ""
                    # push the '$' back onto the scanner
                    string.pushback()
                    # recurse into this scanner again
                    token_list.append( tokenize_variable_ref(string) )
            else:
                token += c

        else:
            assert 0, state

    raise ParseError()

def filter_char(c):
    # make printable char
    if ord(c) < ord(' '):
        return hex(ord(c))
    return c

@depth_checker
def tokenize_recipe(string):
    # Collect characters together into a token. 
    # At token boundary, store token as a Literal. Add to token_list. Reset token.
    # A variable ref is a token boundary, and EOL is a token boundary.
    # At recipe boundary, create a Recipe from the token_list. 
    #   Also store Recipe in recipe_list. Reset token_list.
    # At rule boundary, create a RecipeList from the recipe_list.

    state_start = -1
    state_recipe = 1
    state_lhs_white = 2
    state_seeking_next_recipe = 3
    state_space = 4
    state_dollar = 5
    state_backslash = 6
    
    state = state_start
    token = ""
    token_list = []
    recipe_list = []

    for c in string :
        print("e c={0} state={1} idx={3} token=\"{2}\"".format(
                filter_char(c),state,token,string.idx))
        if state==state_start : 
            # eat leading recipe_prefix
            if c==recipe_prefix :
                state = state_lhs_white
            else:
                raise ParseError()
                
        elif state_lhs_white :
            # Whitespace after the <tab> (or .RECIPEPREFIX) until the first
            # shell-able command is eaten.
            if c in eol : 
                # empty line
                state = state_start
            elif not c in whitespace : 
                string.pushback()
                state = state_recipe

        elif state==state_recipe :
            if c in eol : 
                # save what we've seen so far
                token_list.append( Literal(token) )
                recipe_list.append( Recipe( token_list ) )
                token = ""
                token_list = []
                # TODO handle \r \r\n \n\r \n
                state = state_seeking_next_recipe
            elif c=='#':
                # save what we've seen so far
                token_list.append( Literal(token) )
                recipe_list.append( Recipe( token_list ) )
                token = ""
                token_list = []
                # eat the comment 
                string.pushback()
                comment(string)
                state = state_seeking_next_recipe
            elif c=='$':
                state = state_dollar
            elif c=='\\':
                state = state_backslash
            else:
                token += c

        elif state==state_seeking_next_recipe : 
            if c=='#':
                # eat the comment 
                string.pushback()
                comment(string)
            elif c==recipe_prefix :
                # jump back to start to eat any more leading whitespace
                # (leading whitespace is stripped, trailing whitespace is
                # preserved)
                state.pushback()
                state = state_start
            elif c in whitespace: 
                state = state_space
            elif c in eol : 
                # ignore EOL, continue seeking
                pass
            else:
                # found some other character therefore no next recipe
                # bye!
                string.pushback()
                return RecipeList(recipe_list)

        elif state==state_space : 
            # eat spaces until EOL or !spaces
            # TODO what happens if .RECIPEPREFIX != <tab>? Is <tab> now
            # whitespace?
            if c in eol : 
                state = state_seeking_next_recipe
            elif c=='#' :
                # eat the comment 
                string.pushback()
                comment(string)
                state = state_seeking_next_recipe
            elif not c in whitespace :
                # buh-bye!
                string.pushback()
                return RecipeList(recipe_list)

        elif state==state_dollar : 
            if c=='$':
                # literal $
                token += "$"
            else:
                # save token so far; note no rstrip()!
                token_list.append(Literal(token))
                # restart token
                token = ""

                # jump to variable_ref tokenizer
                # restore "$" + "(" in the string
                string.pushback()
                string.pushback()

                # jump to var_ref tokenizer
                token_list.append( tokenize_variable_ref(string) )

            state=state_recipe

        elif state==state_backslash : 
            # TODO
            assert 0

        else:
            assert 0,state

    # end of string
    # save what we've seen so far
    token_list.append( Literal(token) )
    recipe_list.append( Recipe(token_list) )
    return RecipeList( recipe_list )

class ScannerIterator(object):
    # string iterator that allows look ahead and push back
    def __init__(self,string):
        self.string = string
        self.idx = 0
        self.max_idx = len(self.string)
        self.state_stack = []

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

    def push_state(self):
        self.state_stack.append(self.idx)

    def pop_state(self):
        self.idx = self.state_stack.pop()

    def remain(self):
        # Test/debug method. Return what remains of the string.
        return self.string[self.idx:]

def parse_file(infilename):
    infile = open(infilename)
    all_lines = infile.readlines()
    infile.close()

    s = "".join(all_lines)
    
    my_iter = ScannerIterator(s)

    # TODO
    assert 0

def run_tests_list(tests_list,tokenizer):
    for test in tests_list :
        print("test={0}".format(test))
        s,result = test
        print("s={0}".format(s))
        my_iter = ScannerIterator(s)
        tokens = [ t for t in tokenizer(my_iter)] 
        print( "tokens={0}".format("|".join([t.string for t in tokens])) )

        assert len(tokens)==len(result), (len(tokens),len(result))

        for v in zip(tokens,result):
            print("\"{0}\" \"{1}\"".format(v[0].string,v[1]))
            assert  v[0].string==v[1], v

def variable_ref_test():

    variable_ref_tests = ( 
        # string    result
        ("$(CC)",   ("$(","CC",")")),
        ("$a",   ("$","a",)),
        ("$($$)",      ("$(","$$",")",)),
        ("$($$$$$$)",      ("$(","$$$$$$",")",)),
        ("$( )",   ("$("," ",")")),
        ("$(    )",   ("$(","    ",")")),
        ("$( CC )", ("$("," CC ", ")")),
        ("$(CC$$)",   ("$(","CC$$", ")")),
        ("$($$CC$$)",   ("$(","$$CC$$", ")")),
        ("$($(CC)$$)",   ("$(","$(","CC", "$$",")",")")),
        ("$($$$(CC)$$)",   ("$(","$$","$(","CC",")","$$", ")")),
        ("$(CC$(LD))",   ("$(","CC","$(","LD",")","",")")),
        ("${CC}",   ("${","CC","}")),
        ("$@",      ("$", "@",)),
        ("$<",      ("$", "<",)),
        ("$F",      ("$","F",)),
        ("$F",      ("$","F",)),
        ("$Ff",      ("$","F","f",)),
        ("$F$f",      ("$","F","$","f",)),
        ("$F$f$",      ("$$","$","F","$","f","$$",)),
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

#    run_tests_list( variable_ref_tests, tokenize_variable_ref )
    
    for test in variable_ref_tests : 
        s,v = test
        print("test={0}".format(s))
        my_iter = ScannerIterator(s)

        tokens = tokenize_variable_ref(my_iter)
        print( "tokens={0}".format(str(tokens)) )
        print("\n")

    # this should fail
#    print( "var={0}".format(tokenize_variable_ref(ScannerIterator("$(CC"))) )

def statement_test():
    rules_tests = ( 
        # rule LHS
        ( "all:",    ("all",":")),
        ( "all::",    ("all","::",)),
        # assignment LHS
        ( "all=foo",    ("all","=",)),
        ( "    all  =",    ("all","=")),
        ( "all:=",    ("all",":=",)),
        ( "all::=foo",    ("all","::=",)),
        ( "all?=foo",    ("all","?=",)),
        ( "all+=foo",    ("all","+=",)),
        ( "$(all)+=foo",    ("","$(","all",")","","+=",)),
        ( "qq$(all)+=foo",    ("qq","$(","all",")","","+=",)),
        ( "qq$(all)qq+=foo",    ("qq","$(","all",")","qq","+=",)),

        # kind of ambiguous
        ( "this is a test = ",           ("this is a test","=",) ),
        ( "  this   is   a   test   = ", ("this   is   a   test","=",) ),
        ( "this$(is) $a $test = ",      ("this ","$(","is",")"," ","$","a"," ","$","t","est","=",) ),
        ( "this $(  is  ) $a $test = ",  ("this ","$(","  is  ",")"," ","$","a"," ","$","t","est","=",) ),
        ( "this$(is)$a$(test) : ",       ("this","$(","is",")","","$","a","","$(","test",")","",":",) ),
        ( "this is a test : ",           ("this","is","a","test",":",) ),
        ( "  this   is   a   test   : ", ("this", "is","a","test",":",) ),
        ( "this $(is) $a $test : ",      ("this","$(","is",")","","$","a","","$","t","est","=",) ),

        # yadda yadda yadda
        ( "override all=foo",    ("override","all","=","foo")),

        ( "all:",       ("all",":") ),
        ( "all:foo",    ("all",":","foo")),
        ( "   all :   foo    ", ("all",":","foo")),
        ( "the quick brown fox jumped over lazy dogs : ; ", 
            ("the", "quick", "brown", "fox","jumped","over","lazy","dogs",":", ";", )),
        ( '"foo" : ; ',     ('"foo"',":",";")),
        ('"foo qqq baz" : ;',   ('"foo',"qqq",'baz"',":",";")),
        (r'\foo : ; ',  (r'\foo', ':', ';')),
        (r'foo\  : ; ', (r'foo ',':', ';',)),
        ('@:;@:',       ('@',':',';','@:',)),
        ('I\ have\ spaces : ; @echo $@',    ('I have spaces',':',';','@echo $@',)),
        ('I\ \ \ have\ \ \ three\ \ \ spaces : ; @echo $@', ('I   have   three   spaces',':', ';', '@echo $@' )),
        ('I$(CC)have$(LD)embedded$(OBJ)varref : ; @echo $(subst hello.o,HELLO.O,$(subst ld,LD,$(subst gcc,GCC,$@)))',
            ( 'I', '$(', 'CC', ')', 'have', '$(', 'LD',')','embedded','$(','OBJ',')','varref',':',';',
              '@echo $(subst hello.o,HELLO.O,$(subst ld,LD,$(subst gcc,GCC,$@)))',)
        ),
        ('$(filter %.o,$(files)): %.o: %.c',    
                    ( '', '$(','filter %.o,',
                            '$(','files',')','',
                       ')','',
                          ':','%.o',':','%.c',)),
        ('aa$(filter %.o,bb$(files)cc)dd: %.o: %.c',    
                    ( 'aa', '$(','filter %.o,bb',
                            '$(','files',')','cc',
                       ')','dd',
                          ':','%.o',':','%.c',)),
        ("double-colon1 :: colon2", ("double-colon1","::","colon2")),
        ( "%.tab.c %.tab.h: %.y", ("%.tab.c","%.tab.h",":","%.y")),
        ("foo2:   # hello there; is this comment ignored?",("foo2",":")),
        ("$(shell echo target $$$$) : $(shell echo prereq $$$$)",
            ("","$(","shell echo target $$$$",")","",":","$(shell echo prereq $$$$)",),)
    )
#    for test in rules_tests : 
#        s,result = test
#        my_iter = ScannerIterator(s)
#        tokens = tokenize_assignment_or_rule(my_iter)
#        print( "tokens={0}".format("|".join([t.string for t in tokens])) )

    for test in rules_tests : 
        s,v = test
        print("test={0}".format(s))
        my_iter = ScannerIterator(s)

        tokens = tokenize_assignment_or_rule(my_iter)
        print( "tokens={0}".format(str(tokens)) )
        print("\n")
#    run_tests_list( rules_tests, tokenize_assignment_or_rule)

@depth_checker
def recurse_test(foo,bar,baz):
    recurse_test(foo+1,bar+1,baz+1)

def internal_tests():
    assert isinstance(VarRef([]),Symbol)

    # $($(qq))
    v = VarRef( [VarRef([Literal("qq")]),] )
    print("v={0}".format(str(v)))

    # 
    # Verify my recursion circuit breaker.
    # (Much more shallow than Python's built-in recursion depth checker.)
    #
    try : 
        recurse_test(10,20,30)
    except NestedTooDeep:
        depth_reset()
    else:
        assert 0
    assert depth==0

    # 
    # Verify == operator
    # The equality operator mostly used in regression tests.
    # 
    lit1 = Literal("all")
    lit2 = Literal("all")
    assert lit1==lit2

    lit1 = Literal("all")
    lit2 = Literal("foo")
    assert lit1!=lit2

    for s in rule_operators : 
        op1 = RuleOp(s)
        op2 = RuleOp(s)
        assert op1==op2

    for s in assignment_operators : 
        op1 = AssignOp(s)
        op2 = AssignOp(s)
        assert op1==op2

    exp1 = RuleExpression( ( Expression( (Literal("all"),) ),
                             RuleOp(":"),
                             PrerequisiteList( () ) )
                        ) 
    exp2 = RuleExpression( (  Expression( (Literal("all"),) ),
                             RuleOp(":"),
                             PrerequisiteList( () ) )
                        ) 
    assert exp1==exp2

    exp2 = RuleExpression( (  Expression( (Literal("all"),) ),
                             RuleOp("::"),
                             PrerequisiteList( () ) )
                        ) 
    assert exp1!=exp2

def rule_rhs_test():
    rule_rhs_test_list = (
        # e.g., foo:
        ( "", () ),
        ( "   # this is foo", () ),

        # e.g., foo:all
        ( "all", () ),

        # e.g., foo : this is a test
        ( "this is a test", () ),

        ( "*.h", () ),

        ( "$(objects)", () ),
        ( "Makefile $(objects) link.ld", () ),
        ( "$(SRCS) $(AUX)", () ),
        ( ".c .o .h", () ),

        # target specific assignment
        ( "CC=mycc", () ),
        ( "CC=mycc #this is a comment", () ),
        ( "CC=mycc ; @echo this is part of the string not a recipe", () ),
        ( "CC:=mycc", () ),
        ( "CC::=mycc", () ),
        ( "CC+=mycc", () ),
        ( "CC?=mycc", () ),
        ( "CC!=mycc", () ),

        # static pattern rule TODO
#        ( ": %.o: %.c", () ),

        # order only prereq
        ( "| $(OBJDIR)", () ),
        ( "$(SRC) | $(OBJDIR)", () ),

    )

    for test in rule_rhs_test_list : 
        s,v = test
        print("test={0}".format(s))
        my_iter = ScannerIterator(s)

        tokens = tokenize_rule_prereq_or_assign(my_iter)
        print( "tokens={0}".format(str(tokens)) )

def test():
    internal_tests()
#    variable_ref_test()
#    statement_test()
#    assignment_test()
#    rule_rhs_test()

def main():
    import sys
    for infilename in sys.argv[1:]:
        parse_file(infilename)
    test()

if __name__=='__main__':
    main()

