"""
\033[0;36msuper ini\033[0m
---------

compiles super_ini --> ini

    super_ini.py [input_path] [output_path]
"""

# Syntax Terminology
#
# Items:
# or key, value pairs, are defined as a key string followed by an equals
# sign, followed by it's value. Items are generally placed explicitly inside a
# scope, otherwise they will be implicitly placed inside the `[__global__]` scope.
#
#       key = value
#       key := value
#       key: str = value
#
# When a key is assigned a value it is known internally as a `classification`
#
# Scopes:
# are containers for key, value pairs, and are defined as a character
# string enclosed in square brackets
#
#       [scope]
#       key = value
#
# Internally a scope `defines` its key, value pairs in it's local LUT.
#
# References:
# are used to refer to values placed else where in the document, it is defined
# as a scope identifier followed by the `SCOPE_RESOLUTION_OPERATOR` (`::`)
# followed by a key identifier. References are resolved during the second stage
# of parsing, once all scopes are in the look up table.
#
#       PI := constants::PI
#
# Lookup Tables:
# Scope objects are stored in the `global LUT`.
# Items defined in a scope are stored in that scope object's `local LUT`.
#
#       local_lut = OrderedDict()
#       local_lut['key'] = Value('value', type='str', trace=stack_trace)
#       global_lut = OrderedDict()
#       global_lut['id'] = Scope('id', lut=local_lut, trace=stack_trace)
#
# Closures:
# are called after all scopes have been parsed into the `global LUT`. A closure
# receives a reference to the scope that implements the closure (caller), and
# can directly modify the scope object's `local LUT`.
# Closure calls are defined in the scope header
#
#       ; here the `inline` closure will be called
#       ; and passed the argument `Weapons`
#       [Eirlithrad] :: inline :Weapons
#
# Symbols:
# are essentially keys without a value, they are used to specify the type of a
# key, and closure arguments.
#
#       ; `:Weapons` is a symbol
#       [Eirlithrad] :: inline :Weapons
#       ; `:i32` is a symbol
#       damage: i32 = 355
#       ; can also be written as
#       damage :i32 = 355

import sys

from collections import OrderedDict

env_flags = {'sorted': False}
extern_parsed = []


class Term:
    OKBLUE = '\033[0;36m'
    OKGREEN = '\033[0;32m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'


class Err:
    UNDEFINED = ('E00', 'undefined sequence')
    DUPLICATE_KEY = ('E01', 'key is already classified in scope')
    ILLEGAL_CHAR_KEY = ('E02', 'key contains illegal character')
    ILLEGAL_CHAR_SCOPE = ('E03', 'scope id contains illegal character')
    UNDEFINED_CLOSURE = ('E04', 'undefined closure:')
    CLOSURE_ARGUMENT_ERROR = ('E05', 'not a symbol:')
    STRUCT_INITIALIZATION = ('E06', 'must classify key from abstract scope:')
    TYPE_ERROR = ('E07', 'incorrect type, expected')
    EVAL_ERROR = ('E07', 'python evaluation error:')
    NO_INPUT = ('E08', 'missing input file')
    NO_OUTPUT = ('E09', 'missing output file')


class Warn:
    UNDEFINED_SCOPE_REFERENCE = ('W00', 'could not look up scope reference')
    UNDEFINED_KEY_REFERENCE = ('W01', 'could not look up key reference')
    MULTIPLE_ASSIGNMENT = ('W02', 'multiple assignments in one statement')
    EMPTY_STRUCT = ('W03', 'empty abstract scope declaration')


class Trace:
    """
    Trace objects are used as a way to keep track of where
    parsed objects are located in the original source.
    """
    def __init__(self, path: str, line: int, scope: str, key: str):
        self.path = path
        self.line = line
        self.scope = scope
        self.key = key

    def copy(self) -> object:
        return Trace(self.path, self.line, self.scope, self.key)

    def __repr__(self) -> str:
        tstr = Term.OKBLUE + '  --> ' + Term.ENDC
        tstr += self.path
        tstr += ':' + Term.OKBLUE + str(self.line) + Term.ENDC
        tstr += ' ' + Term.OKGREEN + '[' + self.scope + ']' + Term.ENDC
        return tstr


def fail(error: tuple, trace: Trace = None, extra: str = ''):
    print('{0}{1}error[{2}]:{3} {4} {5}'.format(
          Term.FAIL, Term.BOLD, error[0], Term.ENDC, error[1], extra))

    if trace:
        print(trace)
    print()
    exit(-1)


def warn(warning: tuple, trace: Trace = None, extra: str = ''):
    print('{0}{1}warning[{2}]:{3} {4} {5}'.format(
          Term.WARN, Term.BOLD, warning[0], Term.ENDC, warning[1], extra))

    if trace:
        print(trace)
    print()


class Token:
    COMMENT = ';'
    SPACE = ' '
    NEW_LINE = '\n'
    INDENT = '\t'
    HEX = '0x',
    OCT = '0o',
    BIN = '0b',
    CLOSURE_DELIMITER = ','
    OPEN_SCOPE_DEF = '['
    CLOSE_SCOPE_DEF = ']'
    VALUE_SEPARATOR = '='
    CLOSURE_OPERATOR = '::'
    DOT_OPERATOR = '.'
    SYMBOL_DEFINITION = ':'
    SCOPE_RESOLUTION_OPERATOR = '::'
    ILLEGAL_NAME_CHARS = '=,:\\'


class Value:
    def __init__(self, value, value_type=None, trace=None):
        if value_type == '':
            value_type = None
        self.value = value
        self.type = value_type
        self.trace = trace

    def __repr__(self):
        return self.value


class Scope:
    """
    Scopes are defined with the format:

        [scope_name]
        x =
        y =

    Scopes have their own look up table with the keys classidied
    within them. Scope objects also keep a reference of their id
    in the global look up table, the Trace object of when the
    were parsed, their closures, closure symbols and whether they
    should not be compiled to the final output (internal)
    """
    def __init__(
        self,
        id: str,
        lut: OrderedDict = {},
        internal: bool = False,
        strace: Trace = None
    ):
        self.id = id
        self.internal = internal
        self.lut = lut
        self.trace = strace
        self.closures = []
        self.symbols = []

    def call_closures(self, global_lut: dict):
        """call closure defined in lut[scope]"""
        for closure in self.closures:
            if closure is not None:
                closure(global_lut, self)

    def get_symbols(self, target_symbols: list):
        for symbol in target_symbols:
            if symbol not in self.lut:
                fail(Err.STRUCT_INITIALIZATION, self.trace, symbol)
            yield str(self.lut[symbol])

    def __repr__(self):
        return self.id + str(self.lut)


class Closure:
    """
    Closures are called after all scopes have been parsed into
    the global look up table. A closure receives a reference
    to the global look up table and a reference to the scope
    that implements the closure (caller)

        [scope] :: internal

    [scope] will store a reference to the 'internal' closure and
    will execute it when the look up table has been parsed
    """
    def env() -> dict:
        return dict((k.replace('_', ''), v) for
                    (k, v) in Closure.__dict__.items())

    def internal(global_lut: dict, caller: Scope):
        """internal closure

        Classifies a internal scope in the global lut,
        scope only for internal use, and will not be compiled
        """
        caller.internal = True

    def _eval(global_lut: dict, caller: Scope):
        """eval closure

        Evaluates python expression for all values in
        the caller's lut, and re-assigns the result
        """
        for key in caller.lut:
            try:
                caller.lut[key].value = str(eval(caller.lut[key].value))
            except NameError:
                # Undefined name, do not evaluate, leave as str literal
                pass
            except Exception as e:
                fail(Err.EVAL_ERROR, caller.trace, e.args)

    def include(global_lut: dict, caller: Scope):
        """include closure

        parses a another ini file and includes it in the
        current global lut, file paths are defined in symbols

            [scope] :: include :file :path/file1
        """
        for symbol in caller.symbols:
            try:
                with open(symbol, 'r') as f:
                    # parse file
                    extern_parsed.append(parse(f.read(), symbol))
            except IOError as e:
                fail(Err.NO_INPUT, caller.trace, symbol)

    def setenv(global_lut: dict, caller: Scope):
        """setenv closure

        Stores keys in scope into the compiler envirornment
        to be used during the parsing/compilation process

        Scopes that call setenv are automatically marked internal
        """
        caller.internal = True

        for key in caller.lut:
            env_flags[key] = caller.lut[key].value

    def abstract(global_lut: dict, caller: Scope):
        """abstract closure

        Classifies an abstract scope in the global lut. Scopes that
        'implement' an abstract scope with 'as' or 'inline' closures
        will be forced to classify keys defined in the scope header

            [reference] :: abstract :x :y
            [scope] :: as :reference
            x =
            y =
        """
        if not caller.symbols:
            warn(Warn.EMPTY_STRUCT, caller.trace)

    def _as(global_lut: dict, caller: Scope):
        """Struct enforcement closure

        Ensures scope classifies all keys required in the
        referenced scope such that:

            [reference] :: abstract :x :y
            [scope] :: as :reference
            x = 120

        will fail to compile because scope does not classify y
        """
        if caller.symbols[0] not in global_lut:
            fail(Err.UNDEFINED_CLOSURE, caller.trace, caller.symbols[0])

        target = global_lut[caller.symbols[0]]
        list(caller.get_symbols(target.symbols))

    def inline(global_lut: dict, caller: Scope):
        """Struct inlining closure

        Set value of target abstract scope to value of lut,
        such that:

            [reference] :: abstract :x :y
            [scope] :: inline :reference
            x = 128
            y = 256

        Compiles to:

            [reference]
            scope = 128 256

        Scopes that call inline are automatically
        marked as internal
        """
        caller.internal = True

        if caller.symbols[0] not in global_lut:
            fail(Err.UNDEFINED_CLOSURE, caller.trace, caller.symbols[0])

        target = global_lut[caller.symbols[0]]

        global_lut[target.id].lut[caller.id] = \
            Value(' '.join(list(caller.get_symbols(target.symbols))))


class Type:
    """
    Checks if a str object could be parsed into another type
    """
    LEGAL_INT = '+-0123456789abcdefxo'
    LEGAL_FLOAT = '+-.0123456789e'
    LEGAL_BOOL = ['true', 'false']

    def env() -> dict:
        return dict((k.replace('_', ''), v) for
                    (k, v) in Type.__dict__.items())

    def _str(value: str) -> bool:
        return True

    def _bool(value: str) -> bool:
        return value.lower() in Type.LEGAL_BOOL

    def _int(value: str) -> bool:
        return all(c in Type.LEGAL_INT for c in value.lower())

    def _float(value: str) -> bool:
        return all(c in Type.LEGAL_FLOAT for c in value.lower())

    def i8(value: str) -> bool:
        return Type.__parse_int(value, 7)

    def u8(value: str) -> bool:
        return Type.__parse_uint(value, 8)

    def i16(value: str) -> bool:
        return Type.__parse_int(value, 15)

    def i32(value: str) -> bool:
        return Type.__parse_int(value, 31)

    def i64(value: str) -> bool:
        return Type.__parse_int(value, 63)

    def f32(value: str) -> bool:
        return Type._float(value)

    def f64(value: str) -> bool:
        return Type.f32(value)

    def __parse_int(value: str, size: int) -> bool:
        if not Type._int(value):
            return False
        try:
            # try parsing integer
            if value.startswith(Token.HEX):
                # parse hexadecimal
                #    0x
                value = int(value, 16)
            elif value.startswith(Token.OCT):
                # parse octal
                #    0o
                value = int(value, 8)
            elif value.startswith(Token.BIN):
                # parse binary
                #    0b
                value = int(value, 2)
            else:
                value = int(value)
        except ValueError as e:
            # cannot parse integer,
            # thus value is not an integer
            return False
        # check if integer size fits in max size
        return value.bit_length() <= size

    def __parse_uint(value: str, size: int) -> bool:
        return Type.__parse_int(value, size) and int(value) >= 0


CLOSURES = Closure.env()
TYPES = Type.env()


def closure(global_lut: dict, src: str, trace: Trace):
    """parses a closure call in a scope header,
    sets closure for Scope object
    """
    src = src.strip().split(Token.SPACE)
    closure_id = src[0].strip()

    if closure_id in CLOSURES:
        # the closure id is a valid closure
        # look up the closure id and append a reference to the
        # closure function to the scope's closures list
        global_lut[trace.scope].closures.append(CLOSURES[closure_id])
        if len(src) > 1:
            # parse closure symbols
            for i in range(1, len(src)):
                if Token.SYMBOL_DEFINITION not in src[i]:
                    # syntax error, expected a symbol
                    #    [scope] :: closure symbol  ; NOT OK
                    #    [scope] :: closure :symbol ; OK
                    fail(Err.CLOSURE_ARGUMENT_ERROR, trace, src[i])
                # append symbol to scope's symbols list
                global_lut[trace.scope].symbols.append(src[i][1:])
    else:
        # this closure is not defines in `Closure.env()`
        fail(Err.UNDEFINED_CLOSURE, trace, closure_id)


def scope(global_lut: dict, src: str, trace: Trace) -> str:
    """parses a scope header, returns Scope object"""
    # separate the scope header in key and closures
    src = src.split(Token.CLOSURE_OPERATOR)
    key = src[0].strip()
    # remove scope definition tokens
    key = key.replace(Token.OPEN_SCOPE_DEF, '').replace(Token.CLOSE_SCOPE_DEF, '')

    if any(c in Token.ILLEGAL_NAME_CHARS for c in key):
        # key contains illegal characters that would
        # cause unpredictable behaviour during parsing
        fail(Err.ILLEGAL_CHAR_SCOPE, trace, key)

    # update the trace to use the new scope
    trace.scope = key
    # create a new Scope object with an empty look up table
    global_lut[key] = Scope(key, lut=OrderedDict(), strace=trace)

    if len(src) > 2:
        # syntax error, having multiple CLOSURE_OPERATORS
        #    [scope] :: closure :: closure
        fail(Err.UNDEFINED, trace, src[1:])

    if len(src) > 1:
        # this scope header defines closures
        for closure_def in src[1].split(Token.CLOSURE_DELIMITER):
            # parse each closure
            closure(global_lut, closure_def, trace)
    return trace.scope


def pair(global_lut: dict, src: str, trace: Trace) -> str:
    """parsers a key value pair, returns the key"""
    kv = src.split(Token.VALUE_SEPARATOR)

    if len(kv) > 2:
        # warn about assigning a value twice
        #    key = x = y
        # in this case only the last value will be used
        warn(Warn.MULTIPLE_ASSIGNMENT, trace)

    if len(kv) < 2:
        # key with null value (allowed)
        #    key =
        # the value will be equal to an empty string
        # a standard ini parser might recognize this as
        # a key with a null value
        kv.append('')

    key, value = kv[0].strip(), kv[-1].strip()
    value_type = ''

    if Token.SYMBOL_DEFINITION in key:
        kt = key.split(Token.SYMBOL_DEFINITION)
        key = kt[0].strip()

        if len(kt) == 2:
            value_type = kt[1].strip()

    if any(c in Token.ILLEGAL_NAME_CHARS for c in key):
        # key contains illegal characters that would
        # cause unpredictable behaviour during parsing
        fail(Err.ILLEGAL_CHAR_KEY, trace, key)

    global_lut[trace.scope].lut[key] = Value(value, value_type, trace.copy())
    return key


def replace_reference(global_lut: dict, value: str, trace: Trace) -> str:
    """replaces constant references in values to other keys

    [constants] :: internal
    PI = 3.14159

    [test]
    key = constants::PI

    compiles to:
    [test]
    key = 3.14159
    """
    res = ''

    # split value by Token.SPACE in case the reference
    # is interpolated in the key's value
    for arg in value.split(Token.SPACE):
        # split reference in format `Scope::key` to (Scope, key)
        src = arg.split(Token.SCOPE_RESOLUTION_OPERATOR)

        if len(src) < 2:
            # src does not contain a `Token.SCOPE_RESOLUTION_OPERATOR`
            # re-add the space and continue searching
            res += arg + Token.SPACE
            continue

        if src[0] not in global_lut:
            # src contains a `Token.SCOPE_RESOLUTION_OPERATOR` but
            # the scope referenced does not exist in the look up table
            res += arg + Token.SPACE
            # log a warning, but do not fail with an error since this
            # could just be a string literal which contains the operator
            warn(Warn.UNDEFINED_SCOPE_REFERENCE, trace, src[0])
            continue

        if src[1] not in global_lut[src[0]].lut:
            # src contains a `Token.SCOPE_RESOLUTION_OPERATOR` and
            # the scope referenced exists in the look up table but
            # the key referenced does not exist in the scope's look up table
            res += arg + Token.SPACE
            warn(Warn.UNDEFINED_KEY_REFERENCE, trace, src[1])
            continue

        scope_id, key = src

        # src is a valid reference, look up the scope in the global
        # look up table, and the key in the scope's look up table
        # replacing the src with the key's value
        res += global_lut[scope_id].lut[key].value + Token.SPACE
    return res.strip()


def parse(src: str, path: str) -> dict:
    """parsers super ini source, and returns a look up table"""
    # setup a look up table with a global scope already defined,
    # the global scope is used to store keys that are placed outside
    # a scope in the source
    lut = OrderedDict()
    lut['__global__'] = Scope('__global__')
    # create a trace object for the global scope
    trace = Trace(path, 0, '__global__', '')

    # split the source to parse it line by line
    src = src.split(Token.NEW_LINE)

    for i in range(len(src)):
        # strip comments
        ln = src[i].split(Token.COMMENT)[0]

        if ln == '':
            # skip empty lines
            continue

        # set the current line number in the trace object
        trace.line = i + 1

        if ln.lstrip()[0] == Token.OPEN_SCOPE_DEF:
            # copy trace object so each scope remembers where
            # they are defined in the source
            trace.scope = scope(lut, ln, trace.copy())
            continue

        if Token.VALUE_SEPARATOR not in ln:
            if ln.strip()[0] == Token.SYMBOL_DEFINITION and not lut[trace.scope].lut:
                # this is a symbol placed on a separate line
                #    [scope] :: closure
                #    :symbol
                for symbol in ln.strip().split(Token.SYMBOL_DEFINITION):
                    # loop through each symbol defined in this line
                    # this handles the case:
                    #    [scope] :: closure
                    #    :symbol
                    #    :symbol :symbol
                    # it also strips the SYMBOL_DEFINITION token
                    if (symbol.strip() != ''):
                        # append the symbol to the scopes symbols list
                        lut[trace.scope].symbols.append(symbol.strip())
                continue

            if ln[0] == Token.INDENT or ln[0] == Token.SPACE:
                # this line is a continuation of a key's value
                #    key =
                #      value
                # note tha an indent is required to signify that the
                # line is indeed a continuation of the previous
                # append a SPACE token and the line to the current scope[key]
                lut[trace.scope].lut[trace.key].value += Token.SPACE + ln.strip()
                continue
            # this line does not define symbols, it is not continuation
            # of the previous line, neither does it contain a key, value pair
            fail(Err.UNDEFINED, trace, ln)

        # this line must be a key, value classification
        trace.key = pair(lut, ln, trace)

    for scope_id in lut:
        for key in lut[scope_id].lut:
            obj = lut[scope_id]
            value_obj = obj.lut[key]
            if Token.SCOPE_RESOLUTION_OPERATOR in value_obj.value:
                # this key's value contains one or more
                # references to keys in other look up tables
                value_obj.value = replace_reference(
                    lut, value_obj.value, value_obj.trace)
            if value_obj.type is not None:
                # key has a type, check if the key's value matches this type
                if value_obj.type not in TYPES:
                    # undefined type
                    fail(Err.UNDEFINED, trace, value_obj.type)
                if not TYPES[value_obj.type](value_obj.value):
                    fail(Err.TYPE_ERROR, value_obj.trace, value_obj.type)
        # the global look up table has been parsed
        # now call closures defined in each scope object
        # to finish building the look up table
        lut[scope_id].call_closures(lut)
    return lut


def sorted_keys(lut: dict) -> list:
    """returns sorted lut keys if env_flags[sorted] is set to True"""
    if env_flags['sorted'] is True or str(env_flags['sorted']).lower() == 'true':
        return sorted(lut.keys(), key=lambda x: x)
    return lut.keys()


def compile_text(lut: dict) -> str:
    """compiles a look up table to standard ini"""
    out = ''

    for scope in sorted_keys(lut):
        # get scope object
        obj = lut[scope]

        if obj.internal:
            # do not compile interal scopes
            continue

        # compile scope object in the format:
        # [Scope.id]
        out += Token.OPEN_SCOPE_DEF \
            + obj.id \
            + Token.CLOSE_SCOPE_DEF \
            + Token.NEW_LINE

        # compile scope object's look up table
        for key in sorted_keys(obj.lut):
            value = obj.lut[key].value

            # copile key value pair in the format:
            # key=value
            out += key \
                + Token.VALUE_SEPARATOR \
                + value \
                + Token.NEW_LINE
    return out


def get_stats(lut: dict) -> dict:
    stats = {'objects': 0, 'iobjects': 0, 'keys': 0, 'ikeys': 0}

    for sc in lut:
        stats['objects'] += 1
        if lut[sc].internal:
            stats['iobjects'] += 1
            stats['ikeys'] += len(lut[sc].lut)
        stats['keys'] += len(lut[sc].lut)

    stats['pobjects'] = stats['objects'] - stats['iobjects']
    stats['pkeys'] = stats['keys'] - stats['ikeys']
    return stats


def main(args):
    if len(args) < 1:
        fail(Err.NO_INPUT)

    if args[0] in ('-h', '--help'):
        print(__doc__)
        return

    input_file = args[0]

    try:
        # read and parse source file
        with open(input_file, 'r') as f:
            look_up_table = parse(f.read(), input_file)
    except IOError as e:
        fail(Err.NO_INPUT, extra=e.args)

    for parsed in extern_parsed:
        # update look up table with files parsed externally
        look_up_table.update(parsed)

    stats = get_stats(look_up_table)

    print('{0}{1}OK:{2} parsed {3} objects ({4} internal), {5} keys'.format(
        Term.OKGREEN, Term.BOLD, Term.ENDC,
        stats['objects'], stats['iobjects'], stats['keys']))

    if len(args) < 2:
        # no ouput file provide, assume it is defined in env_flags
        if 'output' not in env_flags:
            fail(Err.NO_OUTPUT)
        output_file = env_flags['output']
    else:
        output_file = args[1]

    # compile lookup table
    compiled = compile_text(look_up_table)

    print('{0}{1}OK:{2} compiled {3} objects, {4} keys'.format(
        Term.OKGREEN, Term.BOLD, Term.ENDC, stats['pobjects'], stats['pkeys']))

    if output_file in ('--dump', '-d'):
        # dump compiled to console
        print('\n{0}output:{1}'.format(Term.OKBLUE, Term.ENDC))
        print(compiled)
        # exit
        return

    try:
        # write compiled to output_file
        with open(output_file, 'w') as f:
            f.write(compiled)
    except IOError as e:
        fail(Err.NO_OUTPUT, extra=e.args)

    print('{0}{1}OK:{2} written to {3}'.format(
        Term.OKGREEN, Term.BOLD, Term.ENDC, output_file))

if __name__ == '__main__':
    print()
    main(sys.argv[1:])
    print()
