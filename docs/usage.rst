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

PRAX Projects consist of a set of Resources, such as Sources, Images, Builds, Tasks, Pipelines, Services and (deployment) Stages. One or more of these resources can be defined in a project specification file that can be used to deploy the resources to the Oceanum.io PRAX platform. 

For a project to be valid and deployable, it must have at least one Stage with at least one deployable Resource such as a Task, a Service or a Pipeline (a Pipeline requires at least one Task).

A single Task or a Service is the representation of a containerized application that can be deployed to the Oceanum.io PRAX platform and it requires at least one Docker Image to be set and a command to be executed within that Image. The difference between a Task and a Service is that a Service is a long-running container that can be accessed via a Route and a Task is a short-lived containerthat can be used as a processing unit to be deployed and executed on its own or within a Pipeline.

The Docker Image for a Task or a Service can be defined from a public Docker Image repository, from a Private Docker Image repository or from a PRAX Build resource defined in the Project specification file.

When defining a PRAX Build resource you have the option to provide directly a base-image and a build command or to connect the Build Resource to a Source-code repository and optionally provide a Dockerfile to be built or an installation script through the source-code. 

When you connect a Source-code repository to a Build Resource, the Oceanum.io PRAX platform will attempt to establish an Webhook connection to the Source-code repository using the Github or Gitlab APIs. The Webhook connection will listen for changes in the Source-code repository and will trigger a new build of the Docker Image when a change is detected in the connected branch or tag.

A minimal Project Specification file should look like this:

.. code-block:: yaml

    name: my-project
    description: My project description
    resources:
        tasks:
        - name: my-task
          image: docker/whalesay:latest
          command: cowsay "Hello World!"
        stages:
        - name: test
          resources:
            tasks:
            - my-task

See full reference for the Project Specification file in the :doc:`reference` section.

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
