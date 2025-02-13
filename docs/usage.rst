CLI Usage Guide
===============

Getting Started
---------------

Install the package:

.. code-block:: console

    $ pip install oceanum-prax

Once the package is installed, you can see the available sub-commands:

.. command-output:: oceanum prax --help

Before starting to use the PRAX commands, we have to login the device to Oceanum.io:

.. code-block:: console

    $ oceanum auth login


Next we can start to use the PRAX commands, for example:

.. code-block:: console

    $ oceanum prax list projects

PRAX Projects
-------------

To create a new project, we need to have a project specification file. 

Here is an example of a PRAX Project Specification file deployment:

.. code-block:: yaml

    name: my-project
    description: My project description
    resources:

        builds:
        - name: app-build
          baseImage: python:3.12-slim
          buildCommand: "pip install flask"

        tasks:
        - name: whalesay
          image: docker/whalesay:latest
          command: cowsay "Hello World!"

        pipelines:
        - name: my-pipeline
          triggers:
            cron:
              # run once a day
              schedule: "0 0 * * *"
          steps:
          - - name: step1
              taskRef: whalesay

        services:
        - name: my-app
          description: Just a flask app example
          image:
            buildRef: app-build
          healthCheck:
            path: /_healthz
            port: 8080
          command: |
            python -c "                                                                                
            import Flask
            app = Flask(__name__)
            @app.route('/')
            def hello():
                return 'Hello World!'
            @app.route('/_healthz')
            def healthz():
                return 'OK'
            app.run(host='0.0.0.0', port=8080)
        
        stages:
        - name: test
          resources:
            services:
            - name: my-app
            pipelines:
            - name: my-pipeline

Deploy an App
-------------



.. code-block:: yaml

    name: my-project
    description: My project description
    resources:
        
        # Connect a Git Source repository to the project
        sources:
        - name: app-source
          description: My source description
          userSecretRef:
            name: my-github-fine-grained-access-token
            key: token
          github:
            repository: '[owner]/[repository]'
            username: '[fine-grained-access-token-username]'

        # Define the image building parameters for the project
        builds:
        - name: app-build
          sourceRef:
            name: app-source
            branch: main
          baseImage: python:3.13
          buildCommand: "pip install -r requirements.txt"

        # Define the An App to be deployed
        services:
        - name: my-app
          description: My app description
          healthCheck:
            path: /health
            port: 8080
          route:
            tier: frontend
          image:
            buildRef: app-build
          command: python app.py
        
        # Deploy the App to two deployment stages, one tracking main branch (test)
        # and the another (prod) tracking v*.*.* tags.
        stages:
        - name: test
          track:
            branch: main
          resources:
            services:
            - name: my-app
        - name: prod
          track:
            # track tags based on REGEX
            tag: 'v\\d+\\.\\d+\\.\\d+'
          resources:
            services:
            - name: my-app  
        
Add the source repository Fine-Grained-Access-Token as a global User Resource so can be used in multiple projects:

.. code-block:: console

    $ oceanum prax create user-secret my-github-fine-grained-access-token --key token --value [fine-grained-access-token]

Alternatively, the token can be specified in the project specification file as:

.. code-block:: yaml

    ...
    resources:
        sources:
        - name: app-source
          description: My source description
          token: '[fine-grained-access-token]'
          github:
            repository: '[owner]/[repository]'
            username: '[fine-grained-access-token-username]'
        ...
Now we can now deploy the project:

.. code-block:: console

    $ oceanum prax deploy prax-project.yaml

Once the project is deployed, you should be able to access the App on the link provided in the output.

When you deploy an App to one or more multiple stages, each deployed staged will generate an unique App or Service Route.

To list the deployed Routes:

.. code-block:: console

    $ oceanum prax list routes
