
# TODO list

## Commands

### Project

- [x] deploy [file] -f specfile -p [project_name] --org [org_name] --user [email] 
- [x] validate [file]
- [x] list projects --search [search] 
- [x] delete project [project_name] --org [org_name]
- [x] describe project [project_name] 
- [x] allow project [project_name] 
- [ ] inspect project [project_name]  (opens ArgoCD UI)

# Route Commands

- [x] list routes
- [x] describe route [route_name]
- [x] update route thumbnail [route_name] -p [project_name] [thumbnail_file]
- [x] allow route [route_name] [subject] --view --change --delete
- [ ] logs route [route_name] -p [project_name] --tail [lines] --follow

#### Secrets/Configmaps Commands

- [ ] list secrets
- [ ] describe secret [secret_name] -p [project_name]
- [ ] create secret [secret_name] -p [project_name] --key [key1] --value [value1] --key [key2] --value [value2]
- [ ] inspect service [service_name] -p [project_name]

### User-Secrets commands

- [ ] list user-secrets
- [ ] create user-secret [secret_name] --key1=value --key2=value
- [ ] update user-secret [secret_name] --key1=value --key2=value
- [ ] delete user-secret [secret_name] 

#### Build Commands

- [x] list builds
- [x] describe build [build_name]
- [ ] submit build 

#### Pipeline Commands

- [x] list pipelines
- [x] describe pipeline [pipeline_name]
- [ ] submit pipeline

#### Tasks Commands

- [x] list tasks
- [x] describe task [task_name]
- [ ] submit task

