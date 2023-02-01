## QA Loop project application API

### Project

The project represents the whole fine tuning project were users will be able to store information related to their work and the models they will be using
#### Attributes
| Name | Type | Description | Example |
| ---- | ---- | ----------- | ------- |
| name |string| project name and must not be longer than 50 characters | `myproject`, `demo` |
| description | text | an optional description for the project no longer than 350 characters | `fine tuning an NLP model` |
| owner | User | the user who created the project owns it | `salim` |
| uuid | string or uuid | auto generated UUID 