Super INI
=========

Super INI is an INI preprocessor, the output produced can be parsed by even the most basic of INI/config parsers, while still allowing a higher level of expression and safety checking.

It was designed with applications that use large INI files in mind, such as games, where INI files are more straight forward to parse and can have a lower memory footprint than other text formats.

```ini
; change compiler settings
[] :: internal, setenv
output = out.ini
sorted = True

[Weapons] :: abstract :damage :level

[Eirlithrad] :: inline :Weapons
damage: i32 = 275
level: u8 = 18

[Melltith] :: eval, inline :Weapons
damage: i32 = 355
level := Eirlithrad::level * 2 - 10
```

#### Compiled output:

```ini
[Weapons]
Eirlithrad=275 18
Melltith=355 26
```

The Super INI compiler is a single Python file with no library dependencies (Python's built-in `sys` and `collections` module are the only required imports)

## Usage

```shell
python3 super_ini.py input_file [output_file]
```

#### options:

- `--help | -h`: display help and exit
- `--dump`: print compiled output

# TOC

- [Specification](#specification)
    - [Include Files](#inlcude-files)
    - [Type Checking](#type-checking)
    - [Multiline Values](#multiline-values)
    - [Referencing Other Items](#referencing-other-items)
    - [Hiding Scopes](#hiding-scopes)
    - [Evaluating Code](#evaluating-code)
    - [Require Classification](#require-classification)
    - [Inlining](#inlining)
    - [Set Compiler Environment](#set-compiler-environment)
- [Syntax Terminology](#syntax-terminology)
    - [Items](#items)
    - [Scopes](#scopes)
    - [References](#references)
    - [Lookup Tables](#lookup-tables)
    - [Closures](#closures)
    - [Symbols](#symbols)

# Specification

## Include Files:

```ini
[] :: include :file0 :file1
```

Parse and include other files to the main output.

File paths that do not exist, or cause an `IOError` while reading will fail with error code `E08`:

```ini
error[E08]: missing input file `file0`
  --> items.ini:1 []
```

## Type Checking:

```ini
_: int   = 780         ; arbitrarily sized integer
_: i8    = 0b01111111  ; 8bit signed integer
_: i16   = 32767       ; 16bit signed integer
_: i32   = 0xFFFF      ; 32bit signed integer
_: i64   = -722        ; 64bit signed integer
_: u8    = 255         ; 8bit unsigned integer
_: float = 3.14159     ; arbitrarily sized floating point number
_: f32   = 1.28e5      ; 32bit floating point number
_: str   = hello world ; a string literal
_: bool  = False       ; True or False
```

Ensure the assigned value is of a specific type.

Values that do not match the specified type will fail with error code `E07`:

```ini
[Melltith]
damage: i32 = "355"
```

```ini
error[E07]: incorrect type, expected i32
  --> items.ini:2 [Melltith]
```

## Multiline Values:

```ini
[] :: include
      :file0
      :file1

[Torlunn]
description =
    Purchased from Scoia'tael merchant in unmarked camp,
    east of Ferry Station in the back of the cave by the
    Distellery in Skellige
```

Continuation lines must be indented to signify they are not another sequence, and should instead be appended to previous line.

Under indented lines will fail with error code `E00`:

```ini
[Torlunn]
description =
    Purchased from Scoia'tael merchant in unmarked camp,
    east of Ferry Station in the back of the cave by the
Distellery in Skellige
```

```ini
error[E00]: undefined sequence `Distellery in Skellige`
  --> items.ini:5 [Torlunn]
```

## Referencing Other Items:

```ini
[constants]
max_damage: i32 = 475

[Harpy]
damage = constants::max_damage
```

Replace a literal with a constant from another scope.

Unresolvable references will print a warning with code `W00` or `W01` depending on which part of the reference could not be resolved:

```ini
[Koviri Cutlass]
damage = constants::min_damage
```

```ini
warning[W01]: could not look up key reference `min_damage`
  --> items.ini:2 [Koviri Cutlass]
```

## Hiding Scopes:

```ini
[Constants] :: internal
max_level: u8 = 46

[Tir Tochair Blade]
key = Constants::max_level
```

#### Compiled output:

```ini
[Tir Tochair Blade]
key=46
```

Any scope marked as `internal` will not be compiled.

## Evaluating Code:

```ini
[constants] :: eval
max_u8 = 2**8 - 1
```

#### Compiled output:

```ini
[constants]
max_u8=255
```

Any scope marked as `eval` will have the value of its keys evaluated.

## Require Classification:

```ini
[Weapon] :: internal, abstract :damage :level

[Weeper] :: as :Weapon
damage: i32 = 370
level: u8 = 31
```

A scope that implements another is forced to classify the `abstract` keys from the scope it implements:

```ini
[Weapon] :: internal, abstract :damage :level

[Weeper] :: as :Weapon
damage: i32 = 370
; missing `level` key, this will not compile
```

If a required key is not classified, the compiler will fail with an error code `E06`:

```ini
error[E06]: must classify key from abstract scope: `level`
  --> items.ini:3 [Weeper]
```

This ensures that if the compiled INI file is being used for deserialization, missing keys will be caught early on instead of causing a runtime error.

## Inlining:

```ini
[Weapons] :: abstract :damage :level

[Disglair] :: inline :Weapons
damage: i32 = 215
level: u8 = 12
```

#### Compiles to:

```ini
[Weapons]
Disglair=215 12
```

This is useful in code that uses an `INI` file to look up function pointers and pass it several arguments. Inlining essentially allows for named parameters in the `Super INI` file.

Scopes marked as `inline` will also be automatically marked as `internal`

Just like `as`, `inline` will cause the compiler to fail with the error code `E06` if an `abstract` key is missing from the `inline` scope.

## Set Compiler Environment:

```ini
[] :: internal, setenv
output = out.ini
sorted = True
```

Items defined in a scope that is marked as `setenv` will be used to update the compiler's global environment.

# Syntax Terminology

Terminology used in the Super INI compiler ([super_ini.py](./super_ini.py))

## Items:

or key, value pairs, are defined as a key string followed by an equals sign, followed by it's value. Items are generally placed explicitly inside a scope, otherwise they will be implicitly placed inside the `[__global__]` scope.

```ini
key = value
key := value
key: str = value
```

When a key is assigned a value it is known internally as a `classification`.

## Scopes:

are containers for key, value pairs, and are defined as a character string enclosed in square brackets

``` ini
[scope]
key = value
```

Internally a scope `defines` its key, value pairs.

## References:

are used to refer to values placed else where in the document, it is defined as a scope identifier followed by the `SCOPE_RESOLUTION_OPERATOR` (`::`) followed by a key identifier. References are resolved during the second stage of parsing, once all scopes are in the look up table.

```ini
PI := constants::PI
```

## Lookup Tables:

Scope objects are stored in the `global LUT`.

Items defined in a scope are stored in that scope object's `local LUT`.

```Python
# example of how super INI is structured within python
local_lut = OrderedDict()
local_lut['key'] = Value('value', type='str', trace=stack_trace)

global_lut = OrderedDict()
global_lut['scope_id'] = Scope('scope_id', lut=local_lut, trace=stack_trace)
```

## Closures:

are called after all scopes have been parsed into the `global LUT`. A closure receives a reference to the scope that implements the closure (caller), and can directly modify the scope object's `local LUT`.

Closure calls are defined in the scope header

```ini
; here the `inline` closure will be called and passed the argument `Weapons`
[Eirlithrad] :: inline :Weapons
```

## Symbols:

are essentially keys without a value, they are used to specify the type of a key, and closure arguments.

```ini
; `:Weapons` is a symbol
[Eirlithrad] :: inline :Weapons
; `:i32` is a symbol
damage: i32 = 355
; can also be written as
damage :i32 = 355
```
