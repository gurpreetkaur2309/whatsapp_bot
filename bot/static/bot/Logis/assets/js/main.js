/**
* Template Name: Logis
* Template URL: https://bootstrapmade.com/logis-bootstrap-logistics-website-template/
* Updated: Aug 07 2024 with Bootstrap v5.3.3
* Author: BootstrapMade.com
* License: https://bootstrapmade.com/license/
*/

(function() {
  "use strict";

  /**
   * Apply .scrolled class to the body as the page is scrolled down
   */
  function toggleScrolled() {
    const selectBody = document.querySelector('body');
    const selectHeader = document.querySelector('#header');
    if (!selectHeader.classList.contains('scroll-up-sticky') && !selectHeader.classList.contains('sticky-top') && !selectHeader.classList.contains('fixed-top')) return;
    window.scrollY > 100 ? selectBody.classList.add('scrolled') : selectBody.classList.remove('scrolled');
  }

  document.addEventListener('scroll', toggleScrolled);
  window.addEventListener('load', toggleScrolled);

  /**
   * Mobile nav toggle
   */
  const mobileNavToggleBtn = document.querySelector('.mobile-nav-toggle');

  function mobileNavToogle() {
    document.querySelector('body').classList.toggle('mobile-nav-active');
    mobileNavToggleBtn.classList.toggle('bi-list');
    mobileNavToggleBtn.classList.toggle('bi-x');
  }
  mobileNavToggleBtn.addEventListener('click', mobileNavToogle);

  /**
   * Hide mobile nav on same-page/hash links
   */
  document.querySelectorAll('#navmenu a').forEach(navmenu => {
    navmenu.addEventListener('click', () => {
      if (document.querySelector('.mobile-nav-active')) {
        mobileNavToogle();
      }
    });

  });

  /**
   * Toggle mobile nav dropdowns
   */
  document.querySelectorAll('.navmenu .toggle-dropdown').forEach(navmenu => {
    navmenu.addEventListener('click', function(e) {
      e.preventDefault();
      this.parentNode.classList.toggle('active');
      this.parentNode.nextElementSibling.classList.toggle('dropdown-active');
      e.stopImmediatePropagation();
    });
  });

  /**
   * Preloader
   */
  

  /**
   * Scroll top button
   */
  let scrollTop = document.querySelector('.scroll-top');

  function toggleScrollTop() {
    if (scrollTop) {
      window.scrollY > 100 ? scrollTop.classList.add('active') : scrollTop.classList.remove('active');
    }
  }
  scrollTop.addEventListener('click', (e) => {
    e.preventDefault();
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  });

  window.addEventListener('load', toggleScrollTop);
  document.addEventListener('scroll', toggleScrollTop);

  /**
   * Animation on scroll function and init
   */
  function aosInit() {
    AOS.init({
      duration: 600,
      easing: 'ease-in-out',
      once: true,
      mirror: false
    });
  }
  window.addEventListener('load', aosInit);

  /**
   * Initiate Pure Counter
   */
  new PureCounter();

  /**
   * Initiate glightbox
   */
  const glightbox = GLightbox({
    selector: '.glightbox'
  });

  /**
   * Init swiper sliders
   */
  function initSwiper() {
    document.querySelectorAll(".init-swiper").forEach(function(swiperElement) {
      let config = JSON.parse(
        swiperElement.querySelector(".swiper-config").innerHTML.trim()
      );

      if (swiperElement.classList.contains("swiper-tab")) {
        initSwiperWithCustomPagination(swiperElement, config);
      } else {
        new Swiper(swiperElement, config);
      }
    });
  }

  window.addEventListener("load", initSwiper);

  /**
   * Frequently Asked Questions Toggle
   */
  document.querySelectorAll('.faq-item h3, .faq-item .faq-toggle').forEach((faqItem) => {
    faqItem.addEventListener('click', () => {
      faqItem.parentNode.classList.toggle('faq-active');
    });
  });

})();
// document.addEventListener('DOMContentLoaded', function() {
//   const ticketInput = document.getElementById('ticket-number');
//   const increaseButton = document.getElementById('increase');
//   const decreaseButton = document.getElementById('decrease');

//   increaseButton.addEventListener('click', function() {
//       let currentValue = parseInt(ticketInput.value);
//       ticketInput.value = currentValue + 1;
//   });

//   decreaseButton.addEventListener('click', function() {
//       let currentValue = parseInt(ticketInput.value);
//       if (currentValue > 1) {
//           ticketInput.value = currentValue - 1;
//       }
//   });

//   const locations = [
//       "ANAND BAZAR",
//       "ANNAPURNA ROAD",
//       "AGRASEN CHAURAHA",
//       "AASARAM BAPU CHAURAHA",
//       "AERODRUM ROAD",
//       "AIRPORT",
//       "A P T C",
//       "BAPAT CHAURAHA",
//       "BADA GANPATI",
//       "BENGALI CHAURAHA",
//       "BHAWAR KUVA",
//       "BHANDARI MILL",
//       "BOMBAY HOSPITAL",
//       "BANGANGA",
//       "CHIMANBHAG",
//       "CHOITHRAM HOSPITAL",
//       "CHANDAN NAGAR",
//       "CHAMELIDEVI SCHOOL",
//       "COLLECTORATE",
//       "DEWAS NAKA",
//       "ELECTRONIC COMPLEX",
//       "INDOGERMAN",
//       "FOOTI KOTHI",
//       "GEETA BHAWAN",
//       "GANGWAL BUS STAND",
//       "GPO",
//       "HAWA BANGLA",
//       "HARSHIDHI",
//       "JANJIR WALA CHAURAHA",
//       "JUNI INDORE",
//       "KHAJRANA",
//       "KRISHNAPURA",
//       "KILA MAIDAN",
//       "LALBAGH",
//       "LOKMANYA NAGAR",
//       "MIG",
//       "MALWA MILL",
//       "MTH",
//       "MHOW NAKA",
//       "MARIMATA CHAURAHA",
//       "MAHESH GAURDLINE",
//       "M Y HOSPITAL",
//       "NEMAWAR ROAD",
//       "NAVALAKHA CHURAHA BUS STOP",
//       "NAGAR NIGAM",
//       "NANDLAL PURA",
//       "NEW PALASIA",
//       "PARK ROAD",
//       "PARDESHIPURA",
//       "PATNIPURA",
//       "PATRAKAR CHAURAHA",
//       "PATEL PRATIMA",
//       "RAILWAY STATION",
//       "RTO",
//       "KHEL PRASHAL / RACE COURSE RD",
//       "RAJENDRA NAGAR",
//       "RAJWADA",
//       "RASOMA LAB",
//       "RADHASWAMI (BILAWALI)",
//       "REGAL SQUARE",
//       "RAJMOHLLA",
//       "SHIVAJI TIRAHA",
//       "SHUBHASH NAGAR",
//       "SANGAM NAGAR",
//       "TEJAJI NAGAR",
//       "TOWER CHAURAHA",
//       "VIJAY NAGAR",
//       "TILAK NAGAR",
//       "WHITE CHURCH",
//       "SHALIMAR TOWNSHIP",
//       "SATYA SAI CHAURAHA",
//       "RAJIV GANDHI CHAURAHA",
//       "BIJALPUR THANA",
//       "RAJENDRA NAGAR THANA",
//       "CAT",
//       "HIGH COURT",
//       "RAJKUMAR BRIDGE",
//       "POLOGROUND",
//       "INDORE WIRE",
//       "KALANI NAGAR",
//       "GANDHI NAGAR",
//       "PALASIA",
//       "EAMALI SAB GURUDWARA",
//       "PIPLYAHANA",
//       "TEEN EAMALI PALDA",
//       "ANTIM CHAURAHA",
//       "MRAGNAYANI",
//       "BHAMORI",
//       "TINPULIA",
//       "NEHRU CHAURAHA",
//       "SANJAY SETU",
//       "NARSINGH BAZAR",
//       "MALGANJ",
//       "SANCHAR NAGAR",
//       "KANADIA",
//       "SEFI",
//       "NEW PALASIA THANA",
//       "LANTERN CHAURAHA",
//       "SARVATE BUS STAND",
//       "MALGODAM PARK ROAD"
//   ];

//   function showSuggestions(input, suggestionsContainer) {
//       const inputValue = input.value.toLowerCase();
//       suggestionsContainer.innerHTML = '';
//       if (inputValue) {
//           const filteredLocations = locations.filter(location => location.toLowerCase().includes(inputValue));
//           filteredLocations.forEach(location => {
//               const suggestionItem = document.createElement('a');
//               suggestionItem.classList.add('list-group-item', 'list-group-item-action');
//               suggestionItem.textContent = location;
//               suggestionItem.onclick = function() {
//                   input.value = location;
//                   suggestionsContainer.innerHTML = '';
//               };
//               suggestionsContainer.appendChild(suggestionItem);
//           });
//           suggestionsContainer.style.display = filteredLocations.length ? 'block' : 'none';
//       } else {
//           suggestionsContainer.style.display = 'none';
//       }
//   }

//   const sourceInput = document.getElementById('source');
//   const sourceSuggestions = document.getElementById('source-suggestions');
//   sourceInput.addEventListener('input', function() {
//       showSuggestions(sourceInput, sourceSuggestions);
//   });

//   const destinationInput = document.getElementById('destination');
//   const destinationSuggestions = document.getElementById('destination-suggestions');
//   destinationInput.addEventListener('input', function() {
//       showSuggestions(destinationInput, destinationSuggestions);
//   });

//   document.addEventListener('click', function(event) {
//       if (!sourceSuggestions.contains(event.target) && event.target !== sourceInput) {
//           sourceSuggestions.style.display = 'none';
//       }
//       if (!destinationSuggestions.contains(event.target) && event.target !== destinationInput) {
//           destinationSuggestions.style.display = 'none';
//       }
//   });
// });

// document.addEventListener('DOMContentLoaded', function() {

  

 

//   const routePriceInput = document.getElementById('route-price');

//   const totalPriceInput = document.getElementById('total-price');


//   // Example route prices (you can replace this with dynamic data)

//   const routePrices = {

//     "ANAND BAZAR": {

//         "ANNAPURNA ROAD": 100,

//         "AGRASEN CHAURAHA": 150,

//         "AASARAM BAPU CHAURAHA": 200,

//         "AERODRUM ROAD": 250,

//         "AIRPORT": 300,

//         // Add more destinations and their prices

//     },

//     "ANNAPURNA ROAD": {

//         "ANAND BAZAR": 100,

//         "AGRASEN CHAURAHA": 120,

//         "AASARAM BAPU CHAURAHA": 180,

//         "AERODRUM ROAD": 230,

//         "AIRPORT": 280,

//         // Add more destinations and their prices

//     },

//     "AGRASEN CHAURAHA": {

//         "ANAND BAZAR": 150,

//         "ANNAPURNA ROAD": 120,

//         "AASARAM BAPU CHAURAHA": 130,

//         "AERODRUM ROAD": 220,

//         "AIRPORT": 270,

//         // Add more destinations and their prices

//     },

//     "AASARAM BAPU CHAURAHA": {

//         "ANAND BAZAR": 200,

//         "ANNAPURNA ROAD": 180,

//         "AGRASEN CHAURAHA": 130,

//         "AERODRUM ROAD": 210,

//         "AIRPORT": 260,

//         // Add more destinations and their prices

//     },

//     "AERODRUM ROAD": {

//         "ANAND BAZAR": 250,

//         "ANNAPURNA ROAD": 230,

//         "AGRASEN CHAURAHA": 220,

//         "AASARAM BAPU CHAURAHA": 210,

//         "AIRPORT": 250,

//         // Add more destinations and their prices

//     },

//     // Continue adding other locations similarly

//     "AIRPORT": {

//         "ANAND BAZAR": 300,

//         "ANNAPURNA ROAD": 280,

//         "AGRASEN CHAURAHA": 270,

//         "AASARAM BAPU CHAURAHA": 260,

//         "AERODRUM ROAD": 250,

//         // Add more destinations and their prices

//     },

//     // Add other locations as needed

//     // ...

// };



//   // Function to update total price

//   function updateTotalPrice() {

//       const ticketCount = parseInt(ticketInput.value);

//       const routePrice = parseFloat(routePriceInput.value) || 0;

//       const totalPrice = ticketCount * routePrice;

//       totalPriceInput.value = totalPrice.toFixed(2);

//   }


//   // Increase ticket count

   


//   // Update route price based on selected source and destination

//   document.getElementById('source').addEventListener('input', function() {

//       const source = this.value;

//       const destination = document.getElementById('destination').value;
//       console.log(source)
//       console.log(destination)
//       if (routePrices[source] && routePrices[source][destination]) {

//           routePriceInput.value = routePrices[source][destination].toFixed(2);

//           updateTotalPrice();

//       } else {

//           routePriceInput.value = "0.00";

//           totalPriceInput.value = "0.00";

//       }

//   });
//   const source = "ANAND BAZAR";

//   const destination = "ANNAPURNA ROAD";

//   document.getElementById('destination').addEventListener('input', function() {

//       const destination = this.value;

//       const source = document.getElementById('source').value;

//       if (routePrices[source] && routePrices[source][destination]) {

//           routePriceInput.value = routePrices[source][destination].toFixed(2);

//           updateTotalPrice();

//       } else {

//           routePriceInput.value = "0.00";

//           totalPriceInput.value = "0.00";

//       }

//   });

// });

// document.addEventListener('DOMContentLoaded', function() {

//   const ticketInput = document.getElementById('ticket-number');

//   const increaseButton = document.getElementById('increase');

//   const decreaseButton = document.getElementById('decrease');

//   const routePriceInput = document.getElementById('route-price');

//   const totalPriceInput = document.getElementById('total-price');


//   // Example route prices

//   const routePrices = {

//       "ANAND BAZAR": {

//           "ANNAPURNA ROAD": 100,

//           "AGRASEN CHAURAHA": 150,

//           "AASARAM BAPU CHAURAHA": 200,

//           "AERODRUM ROAD": 250,

//           "AIRPORT": 300,

//       },

//       "ANNAPURNA ROAD": {

//           "ANAND BAZAR": 100,

//           "AGRASEN CHAURAHA": 120,

//           "AASARAM BAPU CHAURAHA": 180,

//           "AERODRUM ROAD": 230,

//           "AIRPORT": 280,

//       },

//       // Add more routes and their prices here

//   };


//   // Function to update total price

//   function updateTotalPrice() {

//       const ticketCount = parseInt(ticketInput.value);

//       const routePrice = parseFloat(routePriceInput.value) || 0;

//       const totalPrice = ticketCount * routePrice;

//       totalPriceInput.value = totalPrice.toFixed(2);

//   }


//   // Increase ticket count

//   increaseButton.addEventListener('click', function() {

//       let currentValue = parseInt(ticketInput.value);

//       ticketInput.value = currentValue + 1;

//       updateTotalPrice();

//   });


//   // Decrease ticket count

//   decreaseButton.addEventListener('click', function() {

//       let currentValue = parseInt(ticketInput.value);

//       if (currentValue > 1) {

//           ticketInput.value = currentValue - 1;

//           updateTotalPrice();

//       }

//   });


//   // Autocomplete functionality for source and destination

//   const locations = Object.keys(routePrices);

//   const sourceInput = document.getElementById('source');

//   const destinationInput = document.getElementById('destination');

//   const sourceSuggestions = document.getElementById('source-suggestions');

//   const destinationSuggestions = document.getElementById('destination-suggestions');


//   function showSuggestions(input, suggestionsContainer, data) {

//       const inputValue = input.value.toLowerCase();

//       suggestionsContainer.innerHTML = '';

//       if (inputValue) {

//           const filteredLocations = data.filter(location => location.toLowerCase().startsWith(inputValue));

//           filteredLocations.forEach(location => {

//               const suggestionItem = document.createElement('a');

//               suggestionItem.classList.add('list-group-item', 'list-group-item-action');

//               suggestionItem.textContent = location;

//               suggestionItem.onclick = function() {

//                   input.value = location;

//                   suggestionsContainer.innerHTML = '';

//                   suggestionsContainer.style.display = 'none';

//                   updateRoutePrice(); // Update price when a suggestion is selected

//               };

//               suggestionsContainer.appendChild(suggestionItem);

//           });

//           suggestionsContainer.style.display = filteredLocations.length ? 'block' : 'none';

//       } else {

//           suggestionsContainer.style.display = 'none';

//       }

//   }


//   sourceInput.addEventListener('input', function() {

//       showSuggestions(sourceInput, sourceSuggestions, locations);

//   });


//   destinationInput.addEventListener('input', function() {

//       showSuggestions(destinationInput, destinationSuggestions, locations);

//   });


//   document.addEventListener('click', function(event) {

//       if (!sourceSuggestions.contains(event.target) && event.target !== sourceInput) {

//           sourceSuggestions.style.display = 'none';

//       }

//       if (!destinationSuggestions.contains(event.target) && event.target !== destinationInput) {

//           destinationSuggestions.style.display = 'none';

//       }

//   });


//   // Update route price based on selected source and destination

//   function updateRoutePrice() {

//       const source = sourceInput.value;

//       const destination = destinationInput.value;


//       if (routePrices[source] && routePrices[source][destination]) {

//           routePriceInput.value = routePrices[source][destination].toFixed(2);

//           updateTotalPrice();

//       } else {

//           routePriceInput.value = "0.00";

//           totalPriceInput.value = "0.00";

//       }

//   }


//   sourceInput.addEventListener('input', updateRoutePrice);

//   destinationInput.addEventListener('input', updateRoutePrice);

// });


document.addEventListener('DOMContentLoaded', function() {

  const ticketInput = document.getElementById('ticket-number');

  const increaseButton = document.getElementById('increase');

  const decreaseButton = document.getElementById('decrease');

  const routePriceInput = document.getElementById('route-price');

  const totalPriceInput = document.getElementById('total-price');

  const routeSelect = document.getElementById('id_route');


  // Function to update total price

  function updateTotalPrice() {

      const ticketCount = parseInt(ticketInput.value);

      const routePrice = parseFloat(routePriceInput.value) || 0;

      const totalPrice = ticketCount * routePrice;

      totalPriceInput.value = totalPrice.toFixed(2);

  }


  // Increase ticket count

  increaseButton.addEventListener('click', function() {

      let currentValue = parseInt(ticketInput.value);

      ticketInput.value = currentValue + 1;

      updateTotalPrice();

  });


  // Decrease ticket count

  decreaseButton.addEventListener('click', function() {

      let currentValue = parseInt(ticketInput.value);

      if (currentValue > 1) {

          ticketInput.value = currentValue - 1;

          updateTotalPrice();

      }

  });


  // Update route price based on selected route

  routeSelect.addEventListener('change', function() {

      const selectedRouteId = this.value;


      // Fetch the price for the selected route

      if (selectedRouteId) {

          const selectedOption = this.options[this.selectedIndex];

          const pricePerTicket = selectedOption.getAttribute('data-price');

          console.log("Selected Route ID:", selectedRouteId);

          console.log("Price Per Ticket:", pricePerTicket); // Debugging line


          // Update the route price input

          routePriceInput.value = pricePerTicket;

          updateTotalPrice();

      } else {

          routePriceInput.value = "0.00";

          totalPriceInput.value = "0.00";

      }

  });

});