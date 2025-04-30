;; JavaScript language query file for tree-sitter
;; Identifies classes, functions, variables, and modules

(
  (comment)* @doc
  .
  (method_definition
    name: (property_identifier) @name.definition.method) @definition.method
  (#not-eq? @name.definition.method "constructor")
  (#strip! @doc "^[\\s\\*/]+|^[\\s\\*/]$")
  (#select-adjacent! @doc @definition.method)
)

(
  (comment)* @doc
  .
  [
    (class
      name: (_) @name.definition.class)
    (class_declaration
      name: (_) @name.definition.class)
  ] @definition.class
  (#strip! @doc "^[\\s\\*/]+|^[\\s\\*/]$")
  (#select-adjacent! @doc @definition.class)
)

(
  (comment)* @doc
  .
  [
    (function_expression
      name: (identifier) @name.definition.function)
    (function_declaration
      name: (identifier) @name.definition.function)
    (generator_function
      name: (identifier) @name.definition.function)
    (generator_function_declaration
      name: (identifier) @name.definition.function)
  ] @definition.function
  (#strip! @doc "^[\\s\\*/]+|^[\\s\\*/]$")
  (#select-adjacent! @doc @definition.function)
)

(
  (comment)* @doc
  .
  (lexical_declaration
    (variable_declarator
      name: (identifier) @name.definition.variable
      value: [(arrow_function) (function_expression)]) @definition.function)
  (#strip! @doc "^[\\s\\*/]+|^[\\s\\*/]$")
  (#select-adjacent! @doc @definition.function)
)

(
  (comment)* @doc
  .
  (variable_declaration
    (variable_declarator
      name: (identifier) @name.definition.variable
      value: [(arrow_function) (function_expression)]) @definition.function)
  (#strip! @doc "^[\\s\\*/]+|^[\\s\\*/]$")
  (#select-adjacent! @doc @definition.function)
)

;; Variable declarations
(lexical_declaration
  (variable_declarator
    name: (identifier) @name.definition.variable)) @definition.variable

(variable_declaration
  (variable_declarator
    name: (identifier) @name.definition.variable)) @definition.variable

;; Constants
(lexical_declaration
  [
    (variable_declarator
      name: (identifier) @name.definition.constant)
  ]
  (#match? @name.definition.constant "^[A-Z_][A-Z0-9_]*$"))

;; Import/Export
(import_statement
  (import_clause
    [(namespace_import (identifier) @name.definition.module) 
     (named_imports (import_specifier
                     name: (identifier) @name.definition.import))]))

(export_statement
  [(export_clause
    (export_specifier
      name: (identifier) @name.definition.export))
   (identifier) @name.definition.export])

(assignment_expression
  left: [
    (identifier) @name.definition.function
    (member_expression
      property: (property_identifier) @name.definition.function)
  ]
  right: [(arrow_function) (function_expression)]
) @definition.function

(pair
  key: (property_identifier) @name.definition.function
  value: [(arrow_function) (function_expression)]) @definition.function

(
  (call_expression
    function: (identifier) @name.reference.call) @reference.call
  (#not-match? @name.reference.call "^(require)$")
)

(call_expression
  function: (member_expression
    property: (property_identifier) @name.reference.call)
  arguments: (_) @reference.call)

(new_expression
  constructor: (_) @name.reference.class) @reference.class
