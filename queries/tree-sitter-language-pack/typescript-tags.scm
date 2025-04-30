;; TypeScript language query file for tree-sitter
;; Identifies classes, functions, interfaces, variables, and types

(function_signature
  name: (identifier) @name.definition.function) @definition.function

(method_signature
  name: (property_identifier) @name.definition.method) @definition.method

(abstract_method_signature
  name: (property_identifier) @name.definition.method) @definition.method

(abstract_class_declaration
  name: (type_identifier) @name.definition.class) @definition.class

(module
  name: (identifier) @name.definition.module) @definition.module

(interface_declaration
  name: (type_identifier) @name.definition.interface) @definition.interface

(type_annotation
  (type_identifier) @name.reference.type) @reference.type

(new_expression
  constructor: (identifier) @name.reference.class) @reference.class

(function_declaration
  name: (identifier) @name.definition.function) @definition.function

(method_definition
  name: (property_identifier) @name.definition.method) @definition.method

(class_declaration
  name: (type_identifier) @name.definition.class) @definition.class

(interface_declaration
  name: (type_identifier) @name.definition.interface) @definition.interface

(type_alias_declaration
  name: (type_identifier) @name.definition.type) @definition.type

(enum_declaration
  name: (identifier) @name.definition.enum) @definition.enum

;; Variable/Property declarations
(public_property_definition
  name: (property_identifier) @name.definition.field) @definition.field

(property_signature
  name: (property_identifier) @name.definition.field) @definition.field

;; Variables
(variable_declarator
  name: (identifier) @name.definition.variable)

;; Constants
(variable_declarator
  name: (identifier) @name.definition.constant
  (#match? @name.definition.constant "^[A-Z_][A-Z0-9_]*$"))

;; Imports/Exports
(import_clause
  [
    (named_imports
      (import_specifier
        name: (identifier) @name.definition.import))
    (namespace_import
      (identifier) @name.definition.module)
  ])

(export_statement
  declaration: (lexical_declaration
    (variable_declarator
      name: (identifier) @name.definition.export)))

;; References
(call_expression
  function: (identifier) @name.reference.call) @reference.call

(call_expression
  function: (member_expression
    property: (property_identifier) @name.reference.call)) @reference.call 