==================
Commands reference
==================

The library has a command line interface to interact with the datamesh and storage system for bulk operations and administration tasks.

Authentication to Oceanum.io
----------------------------

.. command-output:: oceanum auth --help

Oceanum PRAX commands
---------------------

Main Command
============

.. command-output:: oceanum prax --help

Validate Project specification file
===================================

Validate project specification file

.. command-output:: oceanum prax validate --help

Create or update a project specification file

.. command-output:: oceanum prax deploy --help

Project management commands
===========================

List project specifications

.. command-output:: oceanum prax list projects --help


Describe project

.. command-output:: oceanum prax describe project --help

Update project

.. command-output:: oceanum prax update project --help


Manage project permissions

.. command-output:: oceanum prax allow project --help


Delete project

.. command-output:: oceanum prax delete project --help


Route commands
==============

List services and apps routes

.. command-output:: oceanum prax list routes --help

Describe a service or an app route

.. command-output:: oceanum prax describe route --help

Update service or apps route thumbnail

.. command-output:: oceanum prax update route thumbnail --help

Manage service or app access permissions

.. command-output:: oceanum prax allow route --help


Pipeline commands
=================

List pipelines

.. command-output:: oceanum prax list pipelines --help

Describe pipeline

.. command-output:: oceanum prax describe pipeline --help

Submit pipeline run

.. command-output:: oceanum prax submit pipeline --help

Terminate Pipeline run

.. command-output:: oceanum prax terminate pipeline --help

Retry pipeline run

.. command-output:: oceanum prax retry pipeline --help

Task commands
=============

List tasks

.. command-output:: oceanum prax list tasks --help

Describe task

.. command-output:: oceanum prax describe task --help

Submit task run

.. command-output:: oceanum prax submit task --help

Terminate task run

.. command-output:: oceanum prax terminate task --help

Retry task run

.. command-output:: oceanum prax retry task --help

Build commands
==============

List builds

.. command-output:: oceanum prax list builds --help

Describe build

.. command-output:: oceanum prax describe build --help

Submit build run

.. command-output:: oceanum prax submit build --help

Terminate build run

.. command-output:: oceanum prax terminate build --help

Retry build run

.. command-output:: oceanum prax retry build --help