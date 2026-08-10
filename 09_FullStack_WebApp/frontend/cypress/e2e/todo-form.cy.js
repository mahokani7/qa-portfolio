describe('todo form', () => {
  it('adds a new todo and shows it in the list', () => {
    const createdTodo = {
      id: 'todo-101',
      title: '사이프레스로 할 일 추가 확인',
      completed: false,
    }

    cy.intercept('GET', '/api/to-dos', []).as('getTodos')
    cy.intercept('POST', '/api/to-dos', {
      statusCode: 201,
      body: createdTodo,
    }).as('createTodo')

    cy.visit('/')
    cy.wait('@getTodos')

    cy.get('#todo-title').type(createdTodo.title)
    cy.contains('button', '추가').click()

    cy.wait('@createTodo')
    cy.contains('.todo-item', createdTodo.title).should('be.visible')
  })
})