document.addEventListener('DOMContentLoaded', () => {
    const mainGrid = document.getElementById('main-grid');
    const leftColumn = document.getElementById('left-column');

    let activeGroupId = document.querySelector('.character-group:not(.opacity-0)')?.id;
    
    // A variable to hold the ID of our animation loop
    let animationFrameId = null;

    // ==========================================================================
    // SECTION 1: SIDEBAR EXPANSION & CAROUSEL SYNCHRONIZATION
    // ==========================================================================
    
    /**
     * Instantly updates the carousel's center position. This is called on every
     * frame during the sidebar animation to ensure perfect synchronization.
     */
    function recenterActiveCarouselInstantly() {
        if (activeGroupId) {
            const activeGroupElement = document.getElementById(activeGroupId);
            if (activeGroupElement) {
                updateCarousel(activeGroupElement, true); // instant re-center
            }
        }
    }

    /**
     * Starts a high-performance animation loop that runs for 300ms, matching the
     * CSS transition duration of the sidebar.
     */
    function startAnimationLoop() {
        // Cancel any previous loop to prevent conflicts
        if (animationFrameId) cancelAnimationFrame(animationFrameId);

        const animationDuration = 300; // Must match the CSS transition duration
        let startTime = null;

        // The 'loop' function is called by the browser on every frame.
        const loop = (currentTime) => {
            if (!startTime) startTime = currentTime;
            const elapsedTime = currentTime - startTime;

            recenterActiveCarouselInstantly();

            if (elapsedTime < animationDuration) {
                // If the animation is not finished, request the next frame
                animationFrameId = requestAnimationFrame(loop);
            } else {
                 // Final check to ensure it lands perfectly
                 recenterActiveCarouselInstantly();
            }
        };

        // Start the loop
        animationFrameId = requestAnimationFrame(loop);
    }

    // Event listeners to trigger the synchronized animation.
    leftColumn.addEventListener('mouseenter', () => {
        mainGrid.classList.add('sidebar-expanded');
        startAnimationLoop();
    });

    leftColumn.addEventListener('mouseleave', () => {
        mainGrid.classList.remove('sidebar-expanded');
        startAnimationLoop();
    });

    // ==========================================================================
    // SECTION 2: SEAMLESS CAROUSEL LOGIC
    // ==========================================================================
    const carouselState = {};   // A state object to hold data for each school's unique carousel.
    const CLONE_COUNT = 3;      // The number of cards to clone on each side to create the seamless illusion.

    /**
     * The main function that controls the carousel's appearance and position.
     * @param {HTMLElement} group - The character-group element to update.
     * @param {boolean} instant - If true, the update is immediate (0ms). If false, it's a smooth slide (600ms).
     */
    function updateCarousel(group, instant = false) {
        const slider = group.querySelector('.slider-container');
        const state = carouselState[group.id];

        // Set the animation duration. Clicks get a smooth slide; the sidebar sync gets an instant update.
        slider.style.transitionDuration = instant ? '0ms' : '600ms';
        slider.style.transitionTimingFunction = instant ? '' : 'ease-in-out';
        
        // --- Calculate the new center position ---
        const containerWidth = group.offsetWidth;
        const cardWidth = state.cards[0].offsetWidth;
        const margin = parseInt(window.getComputedStyle(state.cards[0]).marginRight) * 2;
        const cardAndMarginWidth = cardWidth + margin;
        const offsetToCenter = (containerWidth / 2) - (cardAndMarginWidth / 2);
        const newX = offsetToCenter - (state.currentIndex * cardAndMarginWidth);
        
        // Apply the new position to the slider.
        slider.style.transform = `translateX(${newX}px)`;

        // --- Style each card based on whether it is "active" ---
        state.cards.forEach((card, i) => {
            const nameElement = card.querySelector('.character-name');
            const realIndex = (state.currentIndex - CLONE_COUNT + state.totalRealCards) % state.totalRealCards; // identify the true active card, ignoring the clones.
            const cardRealIndex = parseInt(card.dataset.realIndex);

            if (realIndex === cardRealIndex) { // Actived card
                card.style.transform = 'scale(1.15)'; 
                card.style.opacity = '1';
                card.classList.remove('grayscale');
                nameElement.classList.remove('opacity-0', '-translate-x-8');
                nameElement.classList.add('opacity-100', 'translate-x-0');
            } else { // Inactive card
                card.style.transform = 'scale(0.9)';
                card.style.opacity = '0.5';
                card.classList.add('grayscale');
                nameElement.classList.remove('opacity-100', 'translate-x-0');
                nameElement.classList.add('opacity-0', '-translate-x-8');
            }
        });
    }

    // --- One-time setup for each carousel on the page ---
    document.querySelectorAll('.character-group').forEach(group => {
        const slider = group.querySelector('.slider-container');
        const originalCards = Array.from(group.querySelectorAll('.character-card'));
        const totalRealCards = originalCards.length;
        if (totalRealCards === 0) return;

        // Assign a real index to each original card for later identification
        originalCards.forEach((card, i) => card.dataset.realIndex = i);

        // --- Cloning Process for the Seamless Loop ---
        // Take the last CLONE_COUNT=3 cards and add them to the beginning.
        const clonesStart = originalCards.slice(-CLONE_COUNT).map(c => c.cloneNode(true));
        const clonesEnd = originalCards.slice(0, CLONE_COUNT).map(c => c.cloneNode(true));
        slider.append(...clonesEnd);
        slider.prepend(...clonesStart);

        // Initialize the state for this specific carousel.
        const allCards = Array.from(slider.querySelectorAll('.character-card'));
        carouselState[group.id] = {
            currentIndex: CLONE_COUNT, // Start at the first "real" item
            totalRealCards: totalRealCards,
            cards: allCards,
            isTransitioning: false
        };

        // Set the initial position of the carousel.
        setTimeout(() => updateCarousel(group, true), 100);

        // --- Event Listeners for Arrow Navigation ---
        group.querySelector('.nav-left')?.addEventListener('click', () => {
            const state = carouselState[group.id];
            if (state.isTransitioning) return;
            state.currentIndex--;
            updateCarousel(group);
            state.isTransitioning = true;
        });

        group.querySelector('.nav-right')?.addEventListener('click', () => {
            const state = carouselState[group.id];
            if (state.isTransitioning) return;
            state.currentIndex++;
            updateCarousel(group);
            state.isTransitioning = true;
        });

        // --- The "Magic Jump" for the Seamless Loop ---
        // This listener waits for the slide animation to finish.
        slider.addEventListener('transitionend', () => {
            const state = carouselState[group.id];
            state.isTransitioning = false;
            
            // If landed on a clone at the end, silently jump back to the corresponding real card.
            if (state.currentIndex >= state.totalRealCards + CLONE_COUNT) {
                state.currentIndex = CLONE_COUNT;
                updateCarousel(group, true);
            }

            // If landed on a clone at the beginning, silently jump to the corresponding real card.
            if (state.currentIndex < CLONE_COUNT) {
                state.currentIndex = state.totalRealCards + CLONE_COUNT - 1;
                updateCarousel(group, true);
            }
        });
    });

    // ==========================================================================
    // SECTION 3: SCHOOL SELECTION & WINDOW RESIZE
    // ==========================================================================

    // --- Event listener for the school buttons in the left column ---
    const schoolSelectors = document.querySelectorAll('.school-button');
    schoolSelectors.forEach(button => {
        button.addEventListener('click', () => {
            const schoolId = button.dataset.schoolId;
            const newGroupId = `school-group-${schoolId}`;
            if (newGroupId === activeGroupId) return;

            // Update button styles.
            schoolSelectors.forEach(btn => btn.classList.remove('active', 'ring-2', 'ring-sky-400'));
            button.classList.add('active', 'ring-2', 'ring-sky-400');
            
            // Fade out the old group.
            const oldGroup = document.getElementById(activeGroupId);
            if (oldGroup) oldGroup.classList.add('opacity-0', 'pointer-events-none');

            // Fade in the new group.
            const newGroup = document.getElementById(newGroupId);
            if (newGroup) {
                newGroup.classList.remove('opacity-0', 'pointer-events-none');
                updateCarousel(newGroup, true);
                
                // Update our state tracker to the new active group ID.
                activeGroupId = newGroupId; 
            }
        });
    });
    
    // --- Event listener to re-center the carousel when the window is resized ---
    window.addEventListener('resize', () => {
        if (activeGroupId) updateCarousel(document.getElementById(activeGroupId), true);
    });
});