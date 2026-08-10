import { DataTypes, Sequelize } from 'sequelize'
import { defineProjectModel } from './models/Project.js'
import { defineTaskModel } from './models/Task.js'
import { defineUserModel } from './models/User.js'

const sequelizeStorage = process.env.SEQUELIZE_STORAGE || './data/project-management.sqlite'

export const sequelize = new Sequelize({
  dialect: 'sqlite',
  storage: sequelizeStorage,
  logging: false,
})

export const User = defineUserModel(sequelize, DataTypes)
export const Project = defineProjectModel(sequelize, DataTypes)
export const Task = defineTaskModel(sequelize, DataTypes)

User.hasMany(Project, {
  as: 'ownedProjects',
  foreignKey: 'ownerId',
})

Project.belongsTo(User, {
  as: 'owner',
  foreignKey: 'ownerId',
})

Project.hasMany(Task, {
  as: 'tasks',
  foreignKey: 'projectId',
})

Task.belongsTo(Project, {
  as: 'project',
  foreignKey: 'projectId',
})

User.hasMany(Task, {
  as: 'assignedTasks',
  foreignKey: 'assigneeId',
})

Task.belongsTo(User, {
  as: 'assignee',
  foreignKey: 'assigneeId',
})

export async function syncSequelizeModels() {
  await sequelize.sync()
}