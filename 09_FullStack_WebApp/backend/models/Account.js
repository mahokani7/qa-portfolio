import mongoose from 'mongoose'

const accountSchema = new mongoose.Schema(
  {
    ownerName: {
      type: String,
      required: true,
      trim: true,
      maxlength: 100,
    },
    balance: {
      type: Number,
      required: true,
      min: 0,
      default: 0,
    },
  },
  {
    timestamps: true,
    versionKey: false,
    toJSON: {
      transform: (_document, returnedObject) => {
        returnedObject.id = returnedObject._id.toString()
        delete returnedObject._id
      },
    },
  },
)

const Account = mongoose.model('Account', accountSchema)

export default Account