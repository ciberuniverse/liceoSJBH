// Simple carousel logic
(function () {
    const slides = document.getElementById('slides')
    const slideCount = slides.children.length
    const dots = document.getElementById('dots')
    let index = 0
    let interval = null

    // build dots
    for (let i = 0; i < slideCount; i++) {
        const d = document.createElement('div')
        d.className = 'dot' + (i === 0 ? ' active' : '')
        d.dataset.i = i
        d.addEventListener('click', () => { goTo(parseInt(d.dataset.i)) })
        dots.appendChild(d)
    }

    function update() {
        slides.style.transform = `translateX(-${index * 100}%)`
        Array.from(dots.children).forEach((dot, i) => dot.classList.toggle('active', i === index))
        // accessibility
        Array.from(slides.children).forEach((s, i) => s.setAttribute('aria-hidden', i !== index))
    }

    function next() { index = (index + 1) % slideCount; update() }
    function prev() { index = (index - 1 + slideCount) % slideCount; update() }
    function goTo(i) { index = i; update(); resetTimer() }

    document.getElementById('next').addEventListener('click', next)
    document.getElementById('prev').addEventListener('click', prev)

    function startTimer() { interval = setInterval(next, 4000) }
    function resetTimer() { clearInterval(interval); startTimer() }

    startTimer()
    // Pause on hover
    const carousel = document.querySelector('.carousel')
    carousel.addEventListener('mouseenter', () => clearInterval(interval))
    carousel.addEventListener('mouseleave', () => startTimer())

    // keyboard support
    document.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') prev()
        if (e.key === 'ArrowRight') next()
    })
})()