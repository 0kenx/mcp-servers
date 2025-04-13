# Python
def py_func(a): pass
class PyClass: pass
MY_CONST = 10
my_var = "hello"

// JavaScript
function jsFunc(b) { return b; }
class JsClass {}
const JS_CONST = 20;
let jsVar = true;

-- SQL
CREATE FUNCTION sql_func (p INT) RETURNS INT AS $$ BEGIN RETURN p; END; $$ LANGUAGE plpgsql;
CREATE PROCEDURE sql_proc() LANGUAGE SQL AS $$ SELECT 1; $$;

# Shell
sh_func() {
  echo "hello"
}
function other_sh_func {
  ls
}
export SH_VAR=abc

# Basic Import
import os
from mymod import other
require 'some_gem'
use MyApp::Helper;
include <stdio.h>